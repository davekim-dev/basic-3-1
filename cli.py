"""Mini Redis CLI (REPL).

사용자 입력을 읽어 토큰으로 분리하고, 명령어별 인자 개수를 검사해 mini_redis
엔진에 위임한 뒤, 엔진이 돌려준 값을 Redis 스타일 문자열로 출력한다.

즉, 입출력 담당
입력(cli) - 엔진(redis) - 출력(cli)
"""

from mini_redis import MiniRedis, OKStatus, RawText, RedisError

PROMPT = "mini-redis> "
# " " 안에 있으니 리다이랙션X  그냥 mini-redis>(입력 공간) = cli 디자인


def parse_line(line):
    """공백으로 구분된 토큰과 큰따옴표로 감싼 토큰(공백 포함 가능)을 분리한다."""
    tokens = []
    i = 0
    n = len(line)
    while i < n: #흝지 않은 문자가 남아있으면 반복
        while i < n and line[i].isspace():
                                            #isspace(): 공백, 탭 판별   
                                            #' '.isspace()   # True
                                            #'\t'.isspace()  # True
                                            #'a'.isspace()   # False
            i += 1  # 문자가 안 끝난 상태에서 공백,탭이 나오면 넘어가기 
                    # i<n 이 없으면 문자열 끝난 뒤의 공백도 참조하기 때문에 오류!!
        if i >= n:
            break
        if line[i] == '"':
            j = i + 1
            while j < n and line[j] != '"':
                j += 1
            tokens.append(line[i + 1:j]) # 슬라이싱임! " " 을 사이를 뽑아내겠다는 것
                                         # "hello world" => hello world
            i = j + 1
        else:
            j = i
            while j < n and not line[j].isspace():
                j += 1
            tokens.append(line[i:j]) # 공백 없는 문자열만 있는 부분을 슬라이싱
            i = j # 맨 위 while 루프를 위해 커서 옮기는 것
    return tokens
# 결과적으로 tokens라는 list에 문자열을 append 하는 것!
# set A 10 => tokens [set, A, 10]

def format_result(value):
    """엔진이 반환한 값을 Redis 스타일 출력 문자열로 변환한다."""
    # instance(5, int) => True
    # instance(hi, int) => False 앞에 있는 애들이 뒤에 있는 애들에 속하는가?
    if isinstance(value, RedisError):
        return "(error) " + value.message
    if isinstance(value, OKStatus):
        return value.text
    if isinstance(value, RawText):
        return value.text
    if value is None:
        return "(nil)"
    if isinstance(value, int):
        return "(integer) " + str(value)
    if isinstance(value, list):
        if not value:
            return "(empty array)"
        return "\n".join('%d. "%s"' % (i, k) for i, k in enumerate(value, start=1))
    return '"' + value + '"'


def _wrong_args(command):
    return RedisError("ERR wrong number of arguments for '" + command + "' command")


def dispatch(engine, tokens):
    """토큰을 보고 알맞은 엔진 메서드를 호출한다. 인자 개수/명령어 존재 여부를 검증한다."""
    command = tokens[0].upper()

    if command == "SET":
        if len(tokens) != 3: # set A 10 처럼 len(tokens)=3 이기 때문에!
            return _wrong_args("SET")
        return engine.cmd_set(tokens[1], tokens[2])
                    #mini_redis의 함수 cmd_set을 불러오는 것!
                    #def run() 에서 engine = MiniReids 가 되기 때문에 결과적으로
                    #mini_redis.cmd_set(key=token[1], value=token[2]) 으로 작동하는 것

    if command == "GET":
        if len(tokens) != 2: # 명령어 마다 필요한 인자 개수가 다르니까!
            return _wrong_args("GET")
        return engine.cmd_get(tokens[1])

    if command == "DEL":
        if len(tokens) != 2:
            return _wrong_args("DEL")
        return engine.cmd_del(tokens[1])

    if command == "EXISTS":
        if len(tokens) != 2:
            return _wrong_args("EXISTS")
        return engine.cmd_exists(tokens[1])

    if command == "DBSIZE":
        if len(tokens) != 1:
            return _wrong_args("DBSIZE")
        return engine.cmd_dbsize()

    if command == "KEYS":
        if len(tokens) != 1:
            return _wrong_args("KEYS")
        return engine.cmd_keys()

    if command == "EXPIRE":
        if len(tokens) != 3:
            return _wrong_args("EXPIRE")
        return engine.cmd_expire(tokens[1], tokens[2])

    if command == "TTL":
        if len(tokens) != 2:
            return _wrong_args("TTL")
        return engine.cmd_ttl(tokens[1])

    if command == "CONFIG":
        if len(tokens) != 4 or tokens[1].upper() != "SET" or tokens[2].lower() != "maxmemory":
            #upper(), lower()은 대소문자 => tokens[1].uppear() = token[1]에 있는 문자를 대문자로 읽어라!
            return _wrong_args("CONFIG")
        return engine.cmd_config_set_maxmemory(tokens[3])

    if command == "INFO":
        if len(tokens) != 2 or tokens[1].lower() != "memory":
            return _wrong_args("INFO")
        return engine.cmd_info_memory()

    return RedisError("ERR unknown command '" + tokens[0] + "'")
#def dispatch의 반환


def run():
    engine = MiniRedis()
    while True:
        try:
            line = input(PROMPT)
        except EOFError:
            break

        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower() in ("exit", "quit"):
            break

        tokens = parse_line(stripped)
        if not tokens:
            continue

        result = dispatch(engine, tokens)
        print(format_result(result))


if __name__ == "__main__":
    run()
