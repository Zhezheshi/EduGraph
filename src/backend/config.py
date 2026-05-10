from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    dashscope_api_key: str = ""
    llm_model: str = "qwen3.6-flash"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v3"

    chunk_size: int = 600
    chunk_overlap: int = 80
    rag_top_k: int = 5
    alignment_threshold: float = 0.85
    llm_alignment_threshold: float = 0.7
    max_compression_ratio: float = 0.30

    base_dir: Path = Path(__file__).parent / "data"
    textbook_dir: Path = base_dir / "textbooks"
    parsed_dir: Path = base_dir / "parsed"
    graph_dir: Path = base_dir / "graphs"
    integrated_dir: Path = base_dir / "integrated"
    index_dir: Path = base_dir / "index"
    session_dir: Path = base_dir / "sessions"

    model_config = {
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def model_post_init(self, __context):
        for d in [self.textbook_dir, self.parsed_dir, self.graph_dir,
                   self.integrated_dir, self.index_dir, self.session_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
