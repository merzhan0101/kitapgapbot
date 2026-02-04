import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file="book_gap.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        """Создание таблиц в базе данных"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                full_name TEXT,
                wish_book TEXT,
                comment TEXT,
                created_at TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS draws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giver_id INTEGER,
                receiver_id INTEGER,
                draw_date TIMESTAMP,
                FOREIGN KEY (giver_id) REFERENCES users (user_id),
                FOREIGN KEY (receiver_id) REFERENCES users (user_id)
            )
        ''')
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, full_name, wish_book, comment):
        """Добавление или обновление пользователя"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, full_name, wish_book, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, full_name, wish_book, comment, datetime.now()))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка добавления пользователя: {e}")
            return False
    
    def get_user(self, user_id):
        """Получение данных пользователя"""
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone()
    
    def get_all_users(self):
        """Получение всех пользователей"""
        self.cursor.execute('SELECT * FROM users ORDER BY id')
        return self.cursor.fetchall()
    
    def count_users(self):
        """Подсчет количества пользователей"""
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]
    
    def delete_user(self, user_id):
        """Удаление пользователя"""
        self.cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        self.conn.commit()
    
    def clear_all_users(self):
        """Очистка всех пользователей"""
        self.cursor.execute('DELETE FROM users')
        self.cursor.execute('DELETE FROM draws')
        self.conn.commit()
    
    def save_draw(self, giver_id, receiver_id):
        """Сохранение результата жеребьевки"""
        self.cursor.execute('''
            INSERT INTO draws (giver_id, receiver_id, draw_date)
            VALUES (?, ?, ?)
        ''', (giver_id, receiver_id, datetime.now()))
        self.conn.commit()
    
    def get_draw_result(self, giver_id):
        """Получение результата жеребьевки для дарителя"""
        self.cursor.execute('''
            SELECT u.* FROM draws d
            JOIN users u ON d.receiver_id = u.user_id
            WHERE d.giver_id = ?
            ORDER BY d.draw_date DESC
            LIMIT 1
        ''', (giver_id,))
        return self.cursor.fetchone()
    
    def close(self):
        """Закрытие соединения с БД"""
        self.conn.close()