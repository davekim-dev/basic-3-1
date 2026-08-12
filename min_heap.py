"""최소 힙 (Min-Heap).

TTL 관리를 위해 (expire_at, key) 튜플을 담는다. 완전 이진 트리를 배열로
표현하여, 부모/자식 관계를 포인터가 아닌 인덱스 산술만으로 계산한다.

부모 <= 자식

peek() , pop() 할 때 O(1)인 것, push, 유지할 땐 O(log n)
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
    #data[0] : 리스트 중 가장 첫 번째 = peek(가장 작은 원소)

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
            self._data[0] = last  #기존 root를 last로 대체(새로운 root 지정) -> 교체:O(1)
            self._heapify_down(0)
        return top

    def _heapify_up(self, index): 
    # 최소힙 구조를 유지하기 위해서 list에 값 추가할 때마다 진행 O(logn) 어쩔 수 없는 비용
        while index > 0:
            parent = (index - 1) // 2
            # index[3]의 부모는 index[1]!  부모:index[1] 자식:index[2](좌), index[3](우)
            if self._data[index][0] < self._data[parent][0]:
                self._swap(index, parent)
                index = parent
            else:
                break

    def _heapify_down(self, index):  #pop 이후 마지막 배열을 root로 올린 뒤 시작
        size = len(self._data)
        while True: # 리스트 끝까지 확인해야 하니까 True로 진행
            left = 2 * index + 1
            right = 2 * index + 2
            smallest = index
            if left < size and self._data[left][0] < self._data[smallest][0]:
                smallest = left
            # left < size :: 왼쪽 자식이 배열 안에 있는지 확인 (2*index +1 < size)
            # self._data[left][0]<self._data[smallest][0] :: "left 자식"이 "smallest"보다 작으면 
            # smallest =left :: smallest를 left 자식 으로 대입(변경)
            if right < size and self._data[right][0] < self._data[smallest][0]:
                smallest = right
            if smallest == index:  
        # index(자신)이 가장 작다면 smallest :: 비교할 left, right 자식들보다 내가 더 작다면 종료
                break
            self._swap(index, smallest)
            index = smallest

    def _swap(self, i, j):
        self._data[i], self._data[j] = self._data[j], self._data[i]
