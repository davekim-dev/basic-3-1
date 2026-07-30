"""최소 힙 (Min-Heap).

TTL 관리를 위해 (expire_at, key) 튜플을 담는다. 완전 이진 트리를 배열로
표현하여, 부모/자식 관계를 포인터가 아닌 인덱스 산술만으로 계산한다.
"""


class MinHeap:
    """튜플의 첫 번째 원소(expire_at) 기준으로 정렬되는 최소 힙."""

    def __init__(self):
        self._data = []

    def size(self):
        return len(self._data)

    def is_empty(self):
        return len(self._data) == 0

    def peek(self):
        """루트(가장 작은 원소)를 제거하지 않고 확인한다. O(1)."""
        if self.is_empty():
            return None
        return self._data[0]

    def push(self, item):
        """원소를 삽입한다. 맨 끝에 붙인 뒤 위로 올리며 힙 조건을 복구한다. O(log n)."""
        self._data.append(item)
        self._heapify_up(len(self._data) - 1)

    def pop(self):
        """루트(가장 작은 원소)를 꺼낸다. 맨 끝 원소를 루트로 옮긴 뒤
        아래로 내리며 힙 조건을 복구한다. O(log n)."""
        if self.is_empty():
            return None
        top = self._data[0]
        last = self._data.pop()
        if self._data:
            self._data[0] = last
            self._heapify_down(0)
        return top

    def _heapify_up(self, index):
        while index > 0:
            parent = (index - 1) // 2
            if self._data[index][0] < self._data[parent][0]:
                self._swap(index, parent)
                index = parent
            else:
                break

    def _heapify_down(self, index):
        size = len(self._data)
        while True:
            left = 2 * index + 1
            right = 2 * index + 2
            smallest = index
            if left < size and self._data[left][0] < self._data[smallest][0]:
                smallest = left
            if right < size and self._data[right][0] < self._data[smallest][0]:
                smallest = right
            if smallest == index:
                break
            self._swap(index, smallest)
            index = smallest

    def _swap(self, i, j):
        self._data[i], self._data[j] = self._data[j], self._data[i]
