import diarize
import chunker
import roller


def main(file: str):
    diarize.main(file)
    file = file.replace(".mp4", "")
    chunker.main(file)
    roller.main(file)


if __name__ == "__main__":
    import fire

    fire.Fire(main)
