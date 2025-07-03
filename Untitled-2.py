cursor.execute("SELECT SUSER_SNAME(), SYSTEM_USER, USER_NAME()")
print("SQL Identity Check:", cursor.fetchone())