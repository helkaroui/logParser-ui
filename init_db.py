import sqlite3 as sql


class LocalDb:

    def __init__(self, config):
        self.config = config

    def init_db(self):
        """Initializes the database."""
        db = self.get_db()
        with open(self.config["SCHEMA"], mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()
        print("Database init: successfully")

    def show_entries(self):
        db = self.get_db()
        cur = db.execute('select title, text from entries order by id desc')
        entries = cur.fetchall()
        return render_template('show_entries.html', entries=entries)

    def add_entry(self, query, args=()):
        db = self.get_db()
        db.execute(query, args)
        db.commit()
        return 'New entry was successfully posted'

    def get_db(self):
        """Opens a new database connection if there is none yet for the
        current application context.
        """
        return self.connect_db()

    def connect_db(self):
        """Connects to the specific database."""
        rv = sql.connect(self.config['DATABASE'])
        rv.row_factory = self.dict_factory
        return rv

    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def query_db(self, query, args=(), one=False):
        """Queries the database and returns a list of dictionaries."""
        cur = self.get_db().execute(query, args)
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv

    def insert_db(self, query, args=()):
        """Queries the database and returns a list of dictionaries."""
        db = self.get_db()
        cur = db.execute(query, args)
        db.commit()
        return cur.lastrowid


if __name__ == '__main__':
    config = {}
    config["DATABASE"] = 'db/database.db'
    config["SCHEMA"] = 'db/schema.sql'
    db = LocalDb(config)
    db.init_db()
