

def get_pg_url(database:str,
               host:str, port:str="5432",
               username:str="postgres", password:str="postgres") -> str:
    return "postgresql+psycopg://{}:{}@{}:{}/{}".format(username, password, host, port, database)