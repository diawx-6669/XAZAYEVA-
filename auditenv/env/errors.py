"""Bounded error codes. Errors carry only a code: no messages, IDs or data."""

UNKNOWN_TOOL = "unknown_tool"
BAD_ARGS = "bad_args"
NOT_FOUND = "not_found"
INVALID_CURSOR = "invalid_cursor"
CALC_ERROR = "calc_error"
EPISODE_OVER = "episode_over"

CODES = (UNKNOWN_TOOL, BAD_ARGS, NOT_FOUND, INVALID_CURSOR, CALC_ERROR, EPISODE_OVER)


class ToolError(Exception):
    def __init__(self, code: str):
        assert code in CODES
        super().__init__(code)
        self.code = code
