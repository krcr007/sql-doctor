from sqlglot import parse_one,exp
class Analyzer:
    def __init__(self,sql:str):
        self.raw_sql=sql
        self.ast=parse_one(sql)

    def get_tables(self) -> list[str]:
        pass

    def has_select_star(self) -> bool:
        pass

    def get_leading_wildcard_likes(self) -> list[str]:
        issues=[]
        for like_node in self.ast.find_all((exp.Like, exp.ILike)):
            pattern_str=str(like_node.expression).strip("'\"")

            if pattern_str.startswith("%"):
                column_name=str(like_node.this)
                issues.append(f"{column_name} uses leading wildcard pattern '{pattern_str}'")

        return issues



