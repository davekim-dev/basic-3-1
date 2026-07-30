"""이중 연결 리스트.

LRU 순서 추적(mini_redis.py)과 해시맵 체이닝(hash_map.py)에서
공통으로 재사용되는 범용 자료구조다. head/tail에 더미(센티널) 노드를 두어
"리스트가 비어있는가", "노드가 맨 앞/뒤인가"를 따로 분기하지 않고도
모든 삽입/삭제/이동 연산이 O(1)로 처리되도록 한다.
"""


class Node:
    """prev/next 포인터와 임의의 data를 갖는 이중 연결 리스트 노드."""

    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None


class DoublyLinkedList:
    """더미 head/tail 센티널 기반 이중 연결 리스트.

    - 맨 앞(head 방향) = 가장 최근에 삽입/이동된 요소
    - 맨 뒤(tail 방향) = 가장 오래된 요소 (LRU 후보)
    """

    def __init__(self):
        self._head = Node(None)
        self._tail = Node(None)
        self._head.next = self._tail
        self._tail.prev = self._head
        self._size = 0

    def size(self):
        return self._size

    def is_empty(self):
        return self._size == 0

    def insert_front(self, data):
        """맨 앞에 새 노드를 삽입하고 그 노드 참조를 반환한다. O(1)."""
        node = Node(data)
        self._link_after(self._head, node)
        self._size += 1
        return node

    def insert_back(self, data):
        """맨 뒤에 새 노드를 삽입하고 그 노드 참조를 반환한다. O(1)."""
        node = Node(data)
        self._link_after(self._tail.prev, node)
        self._size += 1
        return node

    def remove_front(self):
        """맨 앞 노드를 제거하고 그 data를 반환한다. 비어있으면 None. O(1)."""
        if self.is_empty():
            return None
        node = self._head.next
        self._unlink(node)
        self._size -= 1
        return node.data

    def remove_back(self):
        """맨 뒤 노드를 제거하고 그 data를 반환한다. 비어있으면 None. O(1)."""
        if self.is_empty():
            return None
        node = self._tail.prev
        self._unlink(node)
        self._size -= 1
        return node.data

    def remove_node(self, node):
        """임의의 노드를 참조로 직접 제거한다. 위치 탐색 없이 prev/next만 잇는다. O(1)."""
        self._unlink(node)
        self._size -= 1
        return node.data

    def move_to_front(self, node):
        """이미 리스트에 있는 노드를 맨 앞으로 옮긴다 (LRU 갱신용). O(1)."""
        self._unlink(node)
        self._link_after(self._head, node)

    def iter_nodes(self):
        """맨 앞부터 맨 뒤까지 노드 참조를 순서대로 순회한다 (해시맵 체이닝 탐색용)."""
        current = self._head.next
        while current is not self._tail:
            yield current
            current = current.next

    def _link_after(self, anchor, node):
        node.prev = anchor
        node.next = anchor.next
        anchor.next.prev = node
        anchor.next = node

    def _unlink(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None
