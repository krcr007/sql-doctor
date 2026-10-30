from sqlglot import parse_one,exp
from typing import List
from dataclasses import dataclass

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


    def get_tables(self) -> List[str]:
        tables={table.name for table in self.ast.find_all(exp.Table)}
        return list(tables)

    def has_select_star(self) -> bool:
        return self.ast.find(exp.Star) is not None

    def has_cartesian_product(self) -> bool:
        joins=list(self.ast.find_all(exp.Join))
        for join in joins:
            if not join.args.get("on") and join.kind!="CROSS":
                return True
        return False
