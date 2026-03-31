from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

AppBase = declarative_base()

class AdminUser(AppBase):
    __tablename__ = 'admin_users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

class SidebarBanner(AppBase):
    __tablename__ = 'sidebar_banners'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    image_url = Column(String, nullable=False)
    link_url = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    position = Column(Integer, nullable=False)

class Category(AppBase):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)

class SeoSettings(AppBase):
    __tablename__ = 'seo_settings'

    id = Column(Integer, primary_key=True)
    site_title = Column(String, nullable=False)
    site_description = Column(Text, nullable=True)
    og_image = Column(String, nullable=True)