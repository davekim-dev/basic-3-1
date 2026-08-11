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
# 싱글턴 인스턴스,, OK는 OKstatus라는 객체를 반환함!
# return OK = OKstatus 객체를 반환


class _Entry:
    """data_map에 저장되는 값. 실제 데이터와 LRU 노드 참조를 함께 묶는다.

    거의 모든 key가 접근 시마다 LRU 노드를 갖게 되므로, 별도의 lru_map을
    두는 대신 data_map의 value 자체에 lru_node를 실어 한 번의 조회로
    둘 다 얻는다.
    """

    def __init__(self, value, lru_node=None):
        self.value = value
        self.lru_node = lru_node #노드 객체 자체를 참조 (포인터랑 무관)

# node.data = (key, entry)          # 해시맵 DLL 노드
#entry = _Entry(value, lru_node)   # entry 안에 진짜 값과 lru_node가 있음

# 1. 해시맵 버킷의 체인을 순회해서 node.data[0] == key인 노드를 찾음 (여기까진 맞음, O(체인 길이))
# 2. 찾은 노드의 node.data[1]이 _Entry 객체 (entry)
# 3. entry.value로 실제 값을, entry.lru_node로 LRU DLL 안의 노드 참조를 바로 얻음 → LRU 쪽은 순회 없이 O(1) 접근

class MiniRedis:
    """String 명령어 + 메모리 관리 + TTL 관리를 담당하는 엔진."""

    def __init__(self):
        self.data_map = HashMap()      # key -> _Entry(value, lru_node)
        self.lru_list = DoublyLinkedList()  # 앞 = 최근 사용, 뒤 = 가장 오래됨
        self.ttl_map = HashMap()       # key -> expire_at (초 단위 절대 시각)
        self.ttl_heap = MinHeap()      # (expire_at, key), lazy deletion으로 정리
        self.used_memory = 0
        self.maxmemory = 0
        self.evicted_keys = 0

    # 무조건 사용하는 lru, data는 HashMap entry에
    # 따로 설정해야 하는 ttl은 따로 HashMap에 들어가도록 배치

    # ---------------- String 명령어 ----------------

    def cmd_set(self, key, value):
        self._expire_if_needed(key)
        entry_size = self._entry_size(key, value)
        if self.maxmemory > 0 and entry_size > self.maxmemory:
            return RedisError("OOM command not allowed when used_memory > 'maxmemory'")

        entry = self.data_map.get(key) #key값을 get해서 entry를 가져온 상태
        if entry is not None: #해당 key값에 이미 entry가 있다면, 
            self.used_memory -= self._entry_size(key, entry.value)
            self.ttl_map.remove(key)  # 기존 키를 덮어쓰면 TTL은 초기화(삭제)한다
            entry.value = value 
            # 이미 있는 entry.lru_node도 바꿔버리면 lru_DLL에서 참조값이 없는 node가 생겨버리는 오류!
        else:
            entry = _Entry(value)
            self.data_map.put(key, entry)  #data_map에 key, entry(value, lru_node)를 넘김

        self.used_memory += entry_size
        self._touch_lru(key, entry)  #key와 entry.lru_node /여기서 lru_node가 채워짐
        self._evict_if_needed()
        return OK

    def cmd_get(self, key):
        if self._expire_if_needed(key):  
        #ttl에서 만료되어서 사라졌는가만 확인!!(key-entry가 존재한다는 보장X)
            return None
        entry = self.data_map.get(key) 
        if entry is None:  
        #key값에 해당되는 entry가 있는가?/ 해당 key값으로 set을 안 했거나, del로 지운 경우
            return None
        self._touch_lru(key, entry)  # 성공한 GET만 LRU 갱신
        return entry.value

    def cmd_del(self, key):
        self._expire_if_needed(key)
        if not self.data_map.contains(key):
            return 0
        self._purge_key(key)
        return 1

    def cmd_exists(self, key):
        if self._expire_if_needed(key):   
            return 0  #expire_if_needed 호출에서 방금 만료되어서 지워졌다 = return 0
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
            value = int(bytes_str) #cli.py 에서의 tokens 때문에
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
# map = key에 대응하는 value들 -> key, expire_at(value)
# heap = 정렬 기준 -> expire_at을 기준으로 정렬 -> expire_at , key
# 실제 heap 코드에서도 index[0], paren†[0] 처럼 expire_at 기준을 index0에 둠!!

    def cmd_ttl(self, key):  #이미 만료되었으면: -2 /ttl 설정 없으면: -1 /아직 만료 전이면: 0
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

    @staticmethod  #내부 데코레이터: self인자가 없다!
    def _entry_size(key, value):
        """요구사항의 used_memory 공식: utf-8 바이트 길이 합. 자료구조 오버헤드는 제외."""
        return len(key.encode("utf-8")) + len(value.encode("utf-8"))

    def _touch_lru(self, key, entry):
        """entry를 LRU 리스트 맨 앞으로 옮긴다(없으면 새로 추가). O(1)."""
        if entry.lru_node is None:
            entry.lru_node = self.lru_list.insert_front(key) 
            #lru_node가 없으면 lru_node = lru_list.insert_front 가 리턴하는 값
        else:
            self.lru_list.move_to_front(entry.lru_node)

    def _purge_key(self, key):
        """data/LRU/TTL 모두에서 key의 흔적을 지운다 (used_memory 반영 포함)."""
        entry = self.data_map.get(key)
        if entry is not None:
            self.used_memory -= self._entry_size(key, entry.value)
            if entry.lru_node is not None:
                self.lru_list.remove_node(entry.lru_node)
            self.data_map.remove(key)
        self.ttl_map.remove(key)

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
            entry = self.data_map.get(victim_key)
            if entry is not None:
                self.used_memory -= self._entry_size(victim_key, entry.value)
                self.data_map.remove(victim_key)
            self.ttl_map.remove(victim_key)
            self.evicted_keys += 1
