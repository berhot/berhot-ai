from paths import UPLOADS_DIR

from src.corpus_factory.intake.intake import read_uploads

if __name__ == "__main__":
    sources = read_uploads(UPLOADS_DIR)

    print("Uploads directory:")
    print(UPLOADS_DIR)

    print("Sources:")
    print(sources)

    