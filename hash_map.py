"""해시맵 (체이닝 방식).

내장 dict/set을 쓰지 않고, 버킷 배열(고정 길이 리스트) + 이중 연결 리스트
체이닝으로 직접 구현한다. 로드 팩터가 0.75를 넘으면 버킷을 2배로 늘리고
전체 재해싱한다.
"""

from doubly_linked_list import DoublyLinkedList

_INITIAL_CAPACITY = 8
_LOAD_FACTOR_LIMIT = 0.75


class HashMap:
    """key -> value 를 저장하는 범용 해시맵.

    value로는 문자열뿐 아니라 다른 자료구조의 노드 참조도 저장할 수 있다
    (예: mini_redis.py의 lru_map은 key -> DoublyLinkedList 노드 참조를 저장).
    """

    def __init__(self, initial_capacity=_INITIAL_CAPACITY):
        self._capacity = initial_capacity
        self._buckets = [DoublyLinkedList() for _ in range(self._capacity)]
        self._size = 0

    def size(self):
        return self._size

    def put(self, key, value):
        """key가 있으면 값을 갱신하고, 없으면 새로 추가한다. 평균 O(1)."""
        bucket, node = self._find_node(key)
        if node is not None:
            node.data = (key, value)
            return
        bucket.insert_back((key, value))
        self._size += 1
        if self._size / self._capacity > _LOAD_FACTOR_LIMIT:
            self._resize()

    def get(self, key):
        """key에 대응하는 값을 반환한다. 없으면 None. 평균 O(1)."""
        _, node = self._find_node(key)
        if node is None:
            return None
        return node.data[1]

    def remove(self, key):
        """key를 제거한다. 제거했으면 True, 원래 없었으면 False. 평균 O(1)."""
        bucket, node = self._find_node(key)
        if node is None:
            return False
        bucket.remove_node(node)
        self._size -= 1
        return True

    def contains(self, key):
        """key 존재 여부를 반환한다. 평균 O(1)."""
        _, node = self._find_node(key)
        return node is not None

    def keys(self):
        """저장된 모든 key를 리스트로 반환한다 (순서 보장 없음). O(n)."""
        result = []
        for bucket in self._buckets:
            for node in bucket.iter_nodes():
                result.append(node.data[0])
        return result

    def _hash(self, key, capacity=None):
        """다항식 누적 해시. 31을 곱해 문자열 조합이 버킷에 고르게 분산되게 한다."""
        capacity = capacity if capacity is not None else self._capacity
        h = 0
        for ch in key:
            h = (h * 31 + ord(ch)) % capacity
        return h

    def _find_node(self, key):
        """key가 속한 버킷과, 체인 안에서 key와 일치하는 노드를 찾아 반환한다.

        체인 길이는 로드 팩터로 제한되므로 평균적으로 O(1)에 가깝다.
        """
        index = self._hash(key)
        bucket = self._buckets[index]
        for node in bucket.iter_nodes():
            if node.data[0] == key:
                return bucket, node
        return bucket, None

    def _resize(self):
        """버킷 수를 2배로 늘리고 모든 항목을 새 버킷 기준으로 재해싱한다."""
        old_buckets = self._buckets
        new_capacity = self._capacity * 2
        new_buckets = [DoublyLinkedList() for _ in range(new_capacity)]
        for bucket in old_buckets:
            for node in bucket.iter_nodes():
                key, value = node.data
                index = self._hash(key, new_capacity)
                new_buckets[index].insert_back((key, value))
        self._buckets = new_buckets
        self._capacity = new_capacity
