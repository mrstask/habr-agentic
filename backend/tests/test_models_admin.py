import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin import AdminUser, SidebarBanner, Category, SeoSettings
from app.db.base import AppBase
def test_admin_user_table_creation():
    assert hasattr(AdminUser, '__tablename__') and AdminUser.__tablename__ == 'admin_users'

def test_sidebar_banner_table_creation():
    assert hasattr(SidebarBanner, '__tablename__') and SidebarBanner.__tablename__ == 'sidebar_banners'

def test_category_table_creation():
    assert hasattr(Category, '__tablename__') and Category.__tablename__ == 'categories'

def test_seo_settings_table_creation():
    assert hasattr(SeoSettings, '__tablename__') and SeoSettings.__tablename__ == 'seo_settings'