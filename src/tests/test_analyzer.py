from src.analyzer import Analyzer

q = Analyzer("SELECT * FROM users JOIN orders ON users.id = orders.user_id")
print("Tables:", q.get_tables())
print("Has SELECT *?:", q.has_select_star())

bad_query = Analyzer("SELECT id, name FROM users WHERE email LIKE '%@gmail.com'")
print("Bad query result:", bad_query.get_leading_wildcard_likes())

good_query = Analyzer("SELECT id, name FROM users WHERE email LIKE 'john%'")
print("Good query result:", good_query.get_leading_wildcard_likes())