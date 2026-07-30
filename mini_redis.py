"""Mini Redis 엔진.

hash_map(해시맵), doubly_linked_list(LRU 순서), min_heap(TTL 만료 관리)을
조합해서 String 명령어, 메모리 관리(LRU eviction), TTL 관리를 실제로 수행한다.
결과는 Redis 스타일 문자열이 아니라 "의미"만 반환하고(OK/None/int/list/에러),
그 의미를 화면에 어떻게 찍을지는 cli.py가 결정한다.
"""

import time

from doubly_linked_list import DoublyLinkedList
from hash_map import HashMap
from min_heap import MinHeap


class RedisError:
    """명령어 처리 중 발생한 에러. cli.py에서 "(error) <message>" 형태로 출력된다."""

    def __init__(self, message):
        self.message = message


class OKStatus:
    """SET, CONFIG SET 성공 시 반환되는 "OK" 상태 값."""

    def __init__(self):
        self.text = "OK"


class RawText:
    """INFO memory처럼 이미 줄 단위로 완성된 텍스트를 그대로 출력할 때 쓴다."""

    def __init__(self, text):
        self.text = text


OK = OKStatus()


class MiniRedis:
    """String 명령어 + 메모리 관리 + TTL 관리를 담당하는 엔진."""

    def __init__(self):
        self.data_map = HashMap()      # key -> value (실제 데이터)
        self.lru_map = HashMap()       # key -> lru_list 노드 참조
        self.lru_list = DoublyLinkedList()  # 앞 = 최근 사용, 뒤 = 가장 오래됨
        self.ttl_map = HashMap()       # key -> expire_at (초 단위 절대 시각)
        self.ttl_heap = MinHeap()      # (expire_at, key), lazy deletion으로 정리
        self.used_memory = 0
        self.maxmemory = 0
        self.evicted_keys = 0

    # ---------------- String 명령어 ----------------

    def cmd_set(self, key, value):
        self._expire_if_needed(key)
        entry_size = self._entry_size(key, value)
        if self.maxmemory > 0 and entry_size > self.maxmemory:
            return RedisError("OOM command not allowed when used_memory > 'maxmemory'")

        old_value = self.data_map.get(key)
        if old_value is not None:
            self.used_memory -= self._entry_size(key, old_value)
            self.ttl_map.remove(key)  # 기존 키를 덮어쓰면 TTL은 초기화(삭제)한다

        self.data_map.put(key, value)
        self.used_memory += entry_size
        self._touch_lru(key)
        self._evict_if_needed()
        return OK

    def cmd_get(self, key):
        if self._expire_if_needed(key):
            return None
        value = self.data_map.get(key)
        if value is None:
            return None
        self._touch_lru(key)  # 성공한 GET만 LRU 갱신
        return value

    def cmd_del(self, key):
        self._expire_if_needed(key)
        if not self.data_map.contains(key):
            return 0
        self._purge_key(key)
        return 1

    def cmd_exists(self, key):
        if self._expire_if_needed(key):
            return 0
        return 1 if self.data_map.contains(key) else 0

    def cmd_dbsize(self):
        self._purge_expired()
        return self.data_map.size()

    def cmd_keys(self):
        self._purge_expired()
        return self.data_map.keys()

    # ---------------- 메모리 관리 명령어 ----------------

    def cmd_config_set_maxmemory(self, bytes_str):
        try:
            value = int(bytes_str)
        except ValueError:
            return RedisError("ERR value is not an integer or out of range")
        if value < 0:
            return RedisError("ERR value is not an integer or out of range")
        self.maxmemory = value
        self._evict_if_needed()  # 제한을 낮췄다면 즉시 초과분을 정리
        return OK

    def cmd_info_memory(self):
        self._purge_expired()
        lines = [
            "used_memory:" + str(self.used_memory),
            "maxmemory:" + str(self.maxmemory),
            "evicted_keys:" + str(self.evicted_keys),
        ]
        return RawText("\n".join(lines))

    # ---------------- TTL 명령어 ----------------

    def cmd_expire(self, key, seconds_str): # 0= 설정X , 1= 설정O
        try:
            seconds = int(seconds_str)
        except ValueError:
            return RedisError("ERR value is not an integer or out of range")

        if self._expire_if_needed(key):
            return 0
        if not self.data_map.contains(key):
            return 0

        if seconds <= 0:
            self._purge_key(key)  # 즉시 만료 처리
            return 1

        expire_at = time.time() + seconds
        self.ttl_map.put(key, expire_at)  # 기존 TTL이 있어도 put이 덮어써 갱신된다
        self.ttl_heap.push((expire_at, key))
        return 1

    def cmd_ttl(self, key):
        if self._expire_if_needed(key):
            return -2
        if not self.data_map.contains(key):
            return -2
        expire_at = self.ttl_map.get(key)
        if expire_at is None:
            return -1
        remaining = expire_at - time.time()
        return int(remaining) if remaining > 0 else 0

    # ---------------- 내부 헬퍼 ----------------

    @staticmethod
    def _entry_size(key, value):
        """요구사항의 used_memory 공식: utf-8 바이트 길이 합. 자료구조 오버헤드는 제외."""
        return len(key.encode("utf-8")) + len(value.encode("utf-8"))

    def _touch_lru(self, key):
        """key를 LRU 리스트 맨 앞으로 옮긴다(없으면 새로 추가). O(1)."""
        node = self.lru_map.get(key)
        if node is None:
            node = self.lru_list.insert_front(key)
            self.lru_map.put(key, node)
        else:
            self.lru_list.move_to_front(node)

    def _remove_from_data_and_ttl(self, key):
        value = self.data_map.get(key)
        if value is not None:
            self.used_memory -= self._entry_size(key, value)
            self.data_map.remove(key)
        self.ttl_map.remove(key)

    def _remove_from_lru(self, key):
        node = self.lru_map.get(key)
        if node is not None:
            self.lru_list.remove_node(node)
            self.lru_map.remove(key)

    def _purge_key(self, key):
        """data/LRU/TTL 세 구조 모두에서 key의 흔적을 지운다 (used_memory 반영 포함)."""
        self._remove_from_data_and_ttl(key)
        self._remove_from_lru(key)

    def _expire_if_needed(self, key):
        """key가 TTL을 넘겼으면 즉시 정리한다. 정리했으면 True."""
        expire_at = self.ttl_map.get(key)
        if expire_at is None:
            return False
        if time.time() >= expire_at:
            self._purge_key(key)
            return True
        return False

    def _purge_expired(self):
        """힙의 peek으로 가장 빨리 만료되는 항목부터 확인하며 만료분을 정리한다.

        힙에는 갱신/삭제로 낡아버린 항목이 남아있을 수 있으므로(lazy deletion),
        ttl_map의 현재 expire_at과 비교해 일치할 때만 실제로 제거한다.
        """
        now = time.time()
        while not self.ttl_heap.is_empty():
            expire_at, key = self.ttl_heap.peek()
            if expire_at > now:
                break  # 가장 빠른 것도 아직 안 지났다면 나머지도 모두 안 지났다
            self.ttl_heap.pop()
            current_expire = self.ttl_map.get(key)
            if current_expire is not None and current_expire == expire_at:
                self._purge_key(key)

    def _evict_if_needed(self):
        """maxmemory 초과 시 LRU 리스트 맨 뒤(가장 오래된 키)부터 제거한다."""
        while (
            self.maxmemory > 0
            and self.used_memory > self.maxmemory
            and not self.lru_list.is_empty()
        ):
            victim_key = self.lru_list.remove_back()
            self.lru_map.remove(victim_key)
            self._remove_from_data_and_ttl(victim_key)
            self.evicted_keys += 1
