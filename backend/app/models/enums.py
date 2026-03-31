from enum import IntEnum, Enum

class ArticleStatus(IntEnum):
    DISCOVERED = 0
    EXTRACTED = 1
    TRANSLATED = 2
    PUBLISHED = 3
    USELESS = 4
    DRAFT = 5

class PipelineStep(Enum):
    extraction = 'extraction'
    content_filter = 'content_filter'
    translation = 'translation'
    review_1 = 'review_1'
    proofreading = 'proofreading'
    review_2 = 'review_2'
    image_text_check = 'image_text_check'
    image_gen = 'image_gen'
    vectorize = 'vectorize'
    publish = 'publish'
    deploy = 'deploy'
    mark_useless = 'mark_useless'

class RunStatus(Enum):
    running = 'running'
    completed = 'completed'
    failed = 'failed'
    skipped = 'skipped'