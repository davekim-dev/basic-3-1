"""Mini Redis CLI (REPL).

사용자 입력을 읽어 토큰으로 분리하고, 명령어별 인자 개수를 검사해 mini_redis
엔진에 위임한 뒤, 엔진이 돌려준 값을 Redis 스타일 문자열로 출력한다.
"""

from mini_redis import MiniRedis, OKStatus, RawText, RedisError

PROMPT = "mini-redis> "


def parse_line(line):
    """공백으로 구분된 토큰과 큰따옴표로 감싼 토큰(공백 포함 가능)을 분리한다."""
    tokens = []
    i = 0
    n = len(line)
    while i < n:
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break
        if line[i] == '"':
            j = i + 1
            while j < n and line[j] != '"':
                j += 1
            tokens.append(line[i + 1:j])
            i = j + 1
        else:
            j = i
            while j < n and not line[j].isspace():
                j += 1
            tokens.append(line[i:j])
            i = j
    return tokens


def format_result(value):
    """엔진이 반환한 값을 Redis 스타일 출력 문자열로 변환한다."""
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
        if len(tokens) != 3:
            return _wrong_args("SET")
        return engine.cmd_set(tokens[1], tokens[2])

    if command == "GET":
        if len(tokens) != 2:
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
            return _wrong_args("CONFIG")
        return engine.cmd_config_set_maxmemory(tokens[3])

    if command == "INFO":
        if len(tokens) != 2 or tokens[1].lower() != "memory":
            return _wrong_args("INFO")
        return engine.cmd_info_memory()

    return RedisError("ERR unknown command '" + tokens[0] + "'")


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
