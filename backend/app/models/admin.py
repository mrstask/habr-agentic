from sqlalchemy import Column, Integer, String, Boolean, Text

from app.db.base import Base


class AdminUser(Base):
    __tablename__ = 'admin_users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)


class SidebarBanner(Base):
    __tablename__ = 'sidebar_banners'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    image_url = Column(String, nullable=False)
    link_url = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    position = Column(Integer, nullable=False)


class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)


class SeoSettings(Base):
    __tablename__ = 'seo_settings'

    id = Column(Integer, primary_key=True)
    site_title = Column(String, nullable=False)
    site_description = Column(Text, nullable=True)
    og_image = Column(String, nullable=True)
