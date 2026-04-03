"""
Repositories package for the Habr Agentic Pipeline backend.

This package contains all data access modules organized by domain:
- articles: Article, Tag, Hub, Image, and embedding queries
- pipeline: PipelineRun and AgentConfig queries
- admin: AdminUser queries

Repositories encapsulate all SQLAlchemy queries and provide a clean
interface for services to interact with the database. Each repository
is responsible for a single aggregate root or related entity group.
"""
