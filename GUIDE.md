# Mini Redis 구현 가이드라인

## 1. 과제 목표

`dict`, `collections.OrderedDict` 같은 내장 자료형을 쓰면 몇 분이면 끝날 기능(Key-Value 저장, LRU 캐시, TTL)을 **밑바닥부터 구현**하면서, 아래 4가지를 스스로 코드로 설명할 수 있게 되는 것이 목표다.

1. 해시맵의 해시 함수와 충돌 해결(체이닝)을 구현 코드 기반으로 설명
2. 이중 연결 리스트 + 해시맵 조합이 왜 O(1) LRU 추적을 가능하게 하는지 설명
3. 힙이 TTL(만료 시간) 관리에 적합한 이유 설명
4. 메모리 제한 환경에서 LRU 정책으로 데이터를 제거하는 전체 흐름(used_memory 갱신 포함) 설명

즉, "빠르게 동작하게 만드는 것"보다 "왜 O(1)/O(log n)인지 설명 가능한 상태로 만드는 것"이 평가 기준에 더 가깝다.

---

## 2. 핵심 자료구조 3종 — 개념 정리

### 2.1 이중 연결 리스트 (Doubly Linked List)

- 노드 구조: `prev`, `next`, `data`
- 필요한 메서드와 각각의 역할

| 메서드 | 역할 | 시간복잡도 |
|---|---|---|
| `insert_front` | 맨 앞에 노드 삽입 (LRU에서 "방금 사용됨" 표시) | O(1) |
| `insert_back` | 맨 뒤에 노드 삽입 | O(1) |
| `remove_front` | 맨 앞 노드 제거 | O(1) |
| `remove_back` | 맨 뒤 노드 제거 (LRU 후보 = 가장 오래된 항목) | O(1) |
| `remove_node` | 임의 노드를 리스트 중간에서 제거 (prev/next만 이어붙이면 됨) | O(1) |
| `move_to_front` | 특정 노드를 맨 앞으로 이동 (`remove_node` + `insert_front`) | O(1) |

**왜 O(1)인가**: 배열과 달리 노드끼리 포인터(prev/next)로만 연결되어 있어서, 노드의 실제 메모리 주소(참조)만 알고 있으면 앞뒤 포인터 몇 개만 바꿔치기하면 삽입/삭제/이동이 끝난다. 요소를 옆으로 밀 필요가 없다.

**주의**: `remove_node`가 O(1)이려면 "그 노드가 어디 있는지"를 이미 알고 있어야 한다. 리스트 자체는 순회 없이는 노드 위치를 못 찾으므로, 이 문제는 해시맵이 해결해준다 (2.2, 2.3 참고).

### 2.2 해시맵 (체이닝 방식)

- 주요 메서드: `put`, `get`, `remove`, `contains`, `keys`, `size`

**해시 함수 설계 (예시 — 다항식 누적 해시)**

```
hash(key):
    h = 0
    for ch in key:
        h = (h * 31 + ord(ch)) % bucket_count
    return h
```

- `31` 같은 소수를 곱하는 이유: 비슷한 문자열들이 같은 값으로 몰리지 않고 버킷 전체에 고르게 분산되게 하기 위해서 (분포 균일성).
- `% bucket_count`로 실제 배열 인덱스 범위 안으로 접어 넣는다.

**충돌(collision)**: 서로 다른 키가 같은 인덱스로 매핑되는 상황. 버킷 수가 유한한 이상 필연적으로 발생한다.

**체이닝(chaining)**: 각 버킷 슬롯을 하나의 연결 리스트로 만들어, 같은 인덱스로 충돌한 키들을 그 리스트에 순서대로 이어 붙인다. 이번 과제는 "이중 연결 리스트 재사용"을 권장하므로, 버킷 배열의 각 칸 = `DoublyLinkedList` 인스턴스로 구성하면 자연스럽다.

**로드 팩터(load factor)**

```
load_factor = 저장된_키_개수 / 버킷_개수
```

- `load_factor > 0.75`가 되면 버킷 배열을 2배로 늘리고, **기존에 저장된 모든 키를 새 버킷 수 기준으로 재해싱(rehash)** 해서 다시 분배한다.
- 리사이징을 안 하면 체인이 길어져 `get`/`put`이 사실상 O(n)으로 저하되므로, 평균 O(1)을 유지하려면 필수.

### 2.3 최소 힙 (Min-Heap) — TTL 관리용

- 주요 메서드: `push`, `pop`, `peek`, `size`
- 내부 구현: `_heapify_up`, `_heapify_down`
- 다룰 요소 형태: `(expire_at, key)` 튜플

**완전 이진 트리를 배열로 표현하는 원리**

```
부모 인덱스 i 의 자식 인덱스 = 2i + 1 (왼쪽), 2i + 2 (오른쪽)
자식 인덱스 i 의 부모 인덱스 = (i - 1) // 2
```

포인터 없이 배열 인덱스 산술 연산만으로 트리 구조를 흉내낼 수 있다는 게 핵심.

**`_heapify_up`** (삽입 시 사용)
1. 새 원소를 배열 맨 끝에 추가
2. 부모와 비교해서 더 작으면(min-heap 조건 위반) 교환
3. 루트에 도달하거나 조건을 만족할 때까지 반복 → O(log n)

**`_heapify_down`** (pop 시 사용)
1. 루트(최솟값)를 반환값으로 빼고, 배열 맨 끝 원소를 루트 자리로 옮김
2. 왼쪽/오른쪽 자식 중 더 작은 쪽과 비교해서 자신이 더 크면 교환
3. 리프에 도달하거나 조건을 만족할 때까지 반복 → O(log n)

**왜 힙이 TTL에 적합한가**: "가장 빨리 만료될 키가 무엇인가"를 `peek()`으로 O(1)에 즉시 확인할 수 있다. 배열을 전체 스캔하면 O(n)이 걸리는 것과 대조적이다.

**Lazy Deletion(지연 삭제)이 필요한 이유**: 힙은 "특정 원소를 지목해서 삭제"하는 게 O(n)이다 (배열 어디 있는지 모르므로). 그런데 키에 새로운 EXPIRE가 걸리거나 DEL 되면, 힙 속에는 예전 `(expire_at, key)`가 낡은 상태로 남는다. 해결책: pop할 때 "이 키가 지금도 실제로 이 만료시간을 갖고 있는지"를 데이터 저장소(해시맵)와 대조해서 확인하고, 다르면 그냥 버리고 다음 것을 꺼낸다. 힙에서 즉시 지우는 대신, 나중에 꺼낼 때 걸러내는 방식.

---

## 3. 세 자료구조의 조합 — 왜 O(1) LRU가 되는가

핵심 트릭: **"해시맵에는 값뿐 아니라 연결 리스트 노드의 참조도 같이 저장한다."**

```
data_map:  key -> value                      (실제 데이터)
lru_map:   key -> DLL 노드 참조                (그 키가 리스트의 어느 노드인지)
lru_list:  이중 연결 리스트 (앞 = 최근 사용, 뒤 = 가장 오래됨)
```

- SET/GET 성공 시:
  1. `lru_map`에서 O(1)로 해당 키의 노드를 찾는다
  2. `lru_list.move_to_front(node)` → `remove_node` + `insert_front`, 둘 다 O(1)이므로 전체 O(1)
- 메모리 초과로 제거해야 할 때:
  1. `lru_list.remove_back()`으로 가장 오래된 노드를 O(1)에 얻는다
  2. 그 노드의 key로 `data_map`, `lru_map`, TTL 힙(lazy) 에서도 제거

"연결 리스트만 있으면 노드 위치를 못 찾아 O(n)", "해시맵만 있으면 순서를 못 따져 LRU 판단 불가" → 두 구조가 서로의 약점을 보완해서 조합 전체가 O(1)이 된다는 것이 이 미션의 핵심 통찰이다.

---

## 4. 메모리 관리 + LRU eviction 전체 흐름

```
SET key value 실행 시:

1. 기존 키가 있다면:
   - used_memory에서 기존 key+value 크기를 뺀다
   - 기존 TTL 항목을 무효화(초기화)한다  ← "덮어쓰면 TTL 초기화" 규칙

2. 단일 엔트리 크기 검사:
   entry_size = len(utf8(key)) + len(utf8(value))
   if maxmemory > 0 and entry_size > maxmemory:
       → 저장하지 않고 OOM 에러 반환, 종료

3. 데이터 저장 + used_memory += entry_size
4. LRU 리스트 맨 앞으로 삽입/이동 (move_to_front)

5. while maxmemory > 0 and used_memory > maxmemory:
       victim_key = lru_list.remove_back() 으로 얻은 키
       data_map, lru_map, (TTL 힙은 lazy) 에서 victim_key 제거
       used_memory -= victim_key의 key+value 크기
       evicted_keys += 1
```

**used_memory 계산 공식** (요구사항 그대로)

```
used_memory = Σ ( len(utf8(key)) + len(utf8(value)) )
```

자료구조 자체의 오버헤드(노드, 포인터, 버킷 배열)는 계산에 포함하지 않는다 — 순수하게 "사용자 데이터 크기"만 추적.

---

## 5. 공통 처리 순서 (모든 키 기반 명령어에 적용)

키를 다루는 명령어(GET, SET, DEL, EXISTS, TTL, EXPIRE 등)는 실행 전에 항상 이 순서를 거친다:

```
1. 키가 TTL 힙/저장소 기준으로 "만료됨"인지 확인
2. 만료됐다면 → data_map, lru_map에서 즉시 삭제 → "키 없음"으로 처리
   (이 삭제 자체는 LRU 갱신 대상이 아님 — GET인데 만료로 지워진 경우 LRU 갱신 X)
3. 만료 안 됐다면 → 원래 하려던 연산 수행
```

이 순서를 헬퍼 함수(예: `_evict_if_expired(key)`)로 뽑아서 모든 명령어 핸들러 앞단에서 재사용하면 일관성을 지키기 쉽다.

---

## 6. 구현 순서 제안 (설계 → 구현 순서)

1. **`doubly_linked_list.py`**: 노드 클래스 + 6개 메서드. 단위 테스트로 삽입/삭제/이동이 정말 O(1) 로직인지(포인터 조작만 하는지) 확인.
2. **`hash_map.py`**: 해시 함수 + put/get/remove/contains/keys/size. 버킷 배열의 각 칸은 `doubly_linked_list.py`의 리스트 재사용. 로드 팩터 0.75 초과 시 리사이즈 로직 추가.
3. **`min_heap.py`**: 배열 기반 힙 + `_heapify_up`/`_heapify_down`. `(expire_at, key)` 튜플 비교는 `expire_at` 기준으로만 수행.
4. **`mini_redis.py` (엔진)**: 위 세 모듈을 조합.
   - `data_map` (실제 값 저장)
   - `lru_map` + `lru_list` (LRU 추적)
   - `ttl_heap` (+ lazy deletion 처리)
   - `used_memory`, `maxmemory`, `evicted_keys` 상태값
   - SET/GET/DEL/EXISTS/DBSIZE/KEYS, CONFIG SET maxmemory, INFO memory, EXPIRE/TTL 커맨드 핸들러
5. **`cli.py`**: REPL 루프, 입력 파싱(공백 분리 + 큰따옴표 처리), 에러 표준 포맷 적용, `mini-redis>` 프롬프트.

## 7. 자가 점검 체크리스트

- [ ] `dict`/`set`/`collections`를 해시맵·캐시 대체용으로 쓰지 않았는가
- [ ] 이중 연결 리스트의 6개 메서드가 전부 O(1)인가 (순회 없이 포인터만 조작하는가)
- [ ] 해시맵 로드 팩터 0.75 초과 시 리사이즈 + 재해싱이 동작하는가
- [ ] 힙의 `_heapify_up`/`_heapify_down`이 인덱스 산술만으로 부모/자식을 찾는가
- [ ] SET이 기존 키를 덮어쓸 때 TTL이 초기화되는가
- [ ] GET이 만료된 키를 지울 때 LRU를 갱신하지 않는가 (성공한 GET만 LRU 갱신)
- [ ] DEL이 data/LRU/TTL 세 구조 모두에서 키를 제거하는가
- [ ] 단일 엔트리가 maxmemory보다 크면 저장하지 않고 OOM을 반환하는가
- [ ] evicted_keys가 제거될 때마다 누적되는가
- [ ] 에러 3종(unknown command / wrong number of arguments / not an integer) 포맷이 예시와 일치하는가
