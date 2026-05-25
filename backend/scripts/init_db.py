#!/usr/bin/env python3
"""
SunChat Backend - Initialize Database
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.sql_models import init_db, get_db
from app.config import settings


def main():
    """初始化数据库"""
    print("初始化数据库...")

    # 确保数据目录存在
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)

    # 初始化数据库
    init_db()
    print(f"数据库已创建: {settings.DATABASE_URL}")

    # 创建默认用户
    db = next(get_db())
    try:
        from models.sql_models import User

        # 检查用户是否存在
        user = db.query(User).filter(User.username == "admin").first()
        if not user:
            import hashlib
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            user = User(
                username="admin",
                password_hash=password_hash,
                is_active=True
            )
            db.add(user)
            db.commit()
            print("默认用户已创建: admin / admin123")
        else:
            print("用户已存在")
    finally:
        db.close()


if __name__ == "__main__":
    main()
