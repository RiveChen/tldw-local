#!/usr/bin/env python3
from jinja2 import Template
import json

prompt_template = """
Continue the rolling transcription summary of "{{title}}".  Consider the current context when summarizing the given transcription part.

### Context: {{ context }}
Speaker-Map: {{ speakermap }}

### Transcription part {{ idx }} of {{ len }}, start time {{ start }}:
{{ chunk }}

### Instruction: Structure your reply with a two element list in the following format:

- Speaker-Map: A map of speakers to their names, for example { "SPEAKER 1": "Bob Dole", "SPEAKER 2": "Jane Doe" }
- Next-Context: An updated context for the next part of the transcription. Always include the speakers and the current topics of discussion.
- Summary: A detailed, point-by-point summary of the current transcription.

"""

from langchain.chat_models import ChatOpenAI
from langchain import LLMChain, PromptTemplate
params = {
    "temperature": 0.7,
    "presence_penalty": 1.176,
    "top_p": 0.1,
    "max_tokens": 1024
}
model = ChatOpenAI(model_name='gpt-3.5-turbo', **params)
chain = LLMChain(llm=model, prompt=PromptTemplate(template='{input}', input_variables=['input']))

def main(prefix: str, init_speakers: str = ""):
    the_template = Template(prompt_template)

    split_segments = json.load(open(prefix+'.chunk.json'))
    info = json.load(open(prefix+'.info.json'))

    context = f"""
    SPEAKER 1: Not yet known
    SPEAKER 2: Not yet known
    Video Title: {info['title']}
    Video Description: {info['description'][:1024]}
    """

    speakers = "{ UNKNOWN }"

    f = open(prefix+'.summary.json', 'w')
    idx = 0
    for chunk in split_segments:
        dur = chunk['end'] - chunk['start']
        print(f"{idx}: {dur}s {len(chunk)}")

        prompt = the_template.render(chunk=chunk['text'], start=chunk['start'], end=chunk['end'],
                                     idx=idx, len=len(split_segments), context=context, speakermap=speakers, title=info['title'])
        #print(prompt)

        answer = chain.run(input=prompt)
        new_context = ''
        new_speakers = ''
        summary = ''
        mode = 0

        for line in answer.split('\n'):
            line = line.strip()
            if line.startswith('-'): line = line[1:]

            idx_next_context = line.find('Next-Context:')
            idx_summary = line.find('Summary:')
            idx_speaker_map = line.find('Speaker-Map:')

            if idx_next_context != -1:
                mode = 1
                new_context = line[idx_next_context+14:]
            elif idx_summary != -1:
                mode = 2
                summary = line[idx_summary+9:]
            elif idx_speaker_map != -1:
                new_speakers = line[idx_speaker_map+13:]
                mode = 3
            elif mode == 1:
                new_context += line
            elif mode == 2:
                summary += line
            elif mode == 3:
                new_speakers += line

        if summary == '' or new_context == '' or new_speakers == '':
            print('extraction failed:', new_context, new_speakers, summary)
            exit(1)
        else:
            section = {
                'start': chunk['start'],
                'end': chunk['end'],
                'summary': summary,
                'speakers': new_speakers,
                'context': new_context
            }
            print('## ', new_speakers)
            print('>> ', new_context)
            print(summary)
            print()
            
            f.write(json.dumps(section)+'\n')
            f.flush()

            context = new_context
            speakers = new_speakers

        idx = idx + 1

if __name__ == "__main__":
    import fire
    fire.Fire(main)