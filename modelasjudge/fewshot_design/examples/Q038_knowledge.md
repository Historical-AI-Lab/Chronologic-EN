# Q38 — knowledge (world_context)

Pool `world_qa`; 18 eligible; k = 3 (requested 3); projected 698/2048; fallback False. Answer cap (max_new_tokens) 16, same as zero-shot.

| | type | source | author |
|---|---|---|---|
| exemplar Q543 | abstention | `hvd.hn1eg5` | John R. Nilson |
| exemplar Q126 | inference | `hvd.32044102848413` | Hiram Corson |
| exemplar Q742 | knowledge | `32044082182031` | J. R. McCulloch |
| **target Q38** | knowledge | `hvd.hn5bs8` | Anonymous |

Ground truth (not shown to model): 'the Great Hall of Xerxes'

## 1. Zero-shot, as the pipeline sends it today

**system**

```text
You will be asked to answer a question in a way that fits the beliefs and expository style of a specific historical context. If the context described would not contain enough information to answer the question, respond simply 'insufficient information.' Otherwise, answer in a short phrase of about 2–4 words.
```

**user**

```text
CONTEXT: The following question asks for information from an American encyclopedia published in 1897; your answer should reflect the state of knowledge and style of exposition current at the time.
QUESTION: What is the name of the hall at Persepolis that is described as the largest and most magnificent structure?
ANSWER: 
```

## 2. Few-shot, chat (OpenAI / OpenRouter / HF-instruct)

**system**

```text
You will be asked to answer a question in a way that fits the beliefs and expository style of a specific historical context. If the context described would not contain enough information to answer the question, respond simply 'insufficient information.' Otherwise, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.
```

**user**

```text
CONTEXT: In answering the following question, envision the perspective of Radio up to the Minute, a hobbyist textbook published in 1924 by John R. Nilson, an American radio engineer. Your answer should reflect the knowledge likely available in that volume.
QUESTION: What was the primary advantage of the ferrite rod antenna?
LENGTH: a short phrase of about 2–5 words
ANSWER:
```

**assistant**

```text
insufficient information
```

**user**

```text
CONTEXT: The best answer to the following question is drawn from A Primer of English Verse, a textbook published in 1892 by Hiram Corson, an American professor of literature.
QUESTION: What is the rhyme scheme in the sestet of the following sonnet?

Lawrence, of virtuous father virtuous son,
Now that the fields are dank, and ways are mire,
Where shall we sometimes meet, and by the fire
Help waste a sullen day, what may be won
From the hard season gaining? Time will run
On smoother, till Favonius reinspire
The frozen earth, and clothe in fresh attire
The lily and rose that neither sowed nor spun.
What neat repast shall feast us, light and choice,
Of Attic taste, with wine, whence we may rise
To hear the lute well touched, or artful voice
Warble immortal notes and Tuscan air?
He who of those delights can judge, and spare
To interpose them oft, is not unwise.
LENGTH: a few words
ANSWER:
```

**assistant**

```text
cdceed
```

**user**

```text
CONTEXT: The following question is drawn from McCulloch's Universal Gazetteer, a gazetteer published in 1847 by J. R. McCulloch, a Scottish economist. Answers should be consistent with the knowledge likely contained in that volume.
QUESTION: What is the chief and only port of Japan?
LENGTH: a few words
ANSWER:
```

**assistant**

```text
Nangasaki
```

**user**

```text
CONTEXT: The following question asks for information from an American encyclopedia published in 1897; your answer should reflect the state of knowledge and style of exposition current at the time.
QUESTION: What is the name of the hall at Persepolis that is described as the largest and most magnificent structure?
LENGTH: a short phrase of about 2–4 words
ANSWER:
```

## 3. Few-shot, Talkie-IT literal string

610 reference tokens. 

```text
<|system|>You will be asked to answer a question in a way that fits the beliefs and expository style of a specific historical context. If the context described would not contain enough information to answer the question, respond simply 'insufficient information.' Otherwise, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.<|end|><|user|>CONTEXT: In answering the following question, envision the perspective of Radio up to the Minute, a hobbyist textbook published in 1924 by John R. Nilson, an American radio engineer. Your answer should reflect the knowledge likely available in that volume.
QUESTION: What was the primary advantage of the ferrite rod antenna?
LENGTH: a short phrase of about 2–5 words
ANSWER:<|end|><|assistant|>insufficient information<|end|><|user|>CONTEXT: The best answer to the following question is drawn from A Primer of English Verse, a textbook published in 1892 by Hiram Corson, an American professor of literature.
QUESTION: What is the rhyme scheme in the sestet of the following sonnet?

Lawrence, of virtuous father virtuous son,
Now that the fields are dank, and ways are mire,
Where shall we sometimes meet, and by the fire
Help waste a sullen day, what may be won
From the hard season gaining? Time will run
On smoother, till Favonius reinspire
The frozen earth, and clothe in fresh attire
The lily and rose that neither sowed nor spun.
What neat repast shall feast us, light and choice,
Of Attic taste, with wine, whence we may rise
To hear the lute well touched, or artful voice
Warble immortal notes and Tuscan air?
He who of those delights can judge, and spare
To interpose them oft, is not unwise.
LENGTH: a few words
ANSWER:<|end|><|assistant|>cdceed<|end|><|user|>CONTEXT: The following question is drawn from McCulloch's Universal Gazetteer, a gazetteer published in 1847 by J. R. McCulloch, a Scottish economist. Answers should be consistent with the knowledge likely contained in that volume.
QUESTION: What is the chief and only port of Japan?
LENGTH: a few words
ANSWER:<|end|><|assistant|>Nangasaki<|end|><|user|>CONTEXT: The following question asks for information from an American encyclopedia published in 1897; your answer should reflect the state of knowledge and style of exposition current at the time.
QUESTION: What is the name of the hall at Persepolis that is described as the largest and most magnificent structure?
LENGTH: a short phrase of about 2–4 words
ANSWER:<|end|><|assistant|>
```

## 4. Few-shot, completion (Talkie-base, HF base models)

569 reference tokens. Stop strings: `'\n* * *'`, `'\nCONTEXT:'`, `'<|endoftext|>'`, `'<|end|>'`, `'<|user|>'`.

```text
You will be asked to answer a question in a way that fits the beliefs and expository style of a specific historical context. If the context described would not contain enough information to answer the question, respond simply 'insufficient information.' Otherwise, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.

* * *

CONTEXT: In answering the following question, envision the perspective of Radio up to the Minute, a hobbyist textbook published in 1924 by John R. Nilson, an American radio engineer. Your answer should reflect the knowledge likely available in that volume.
QUESTION: What was the primary advantage of the ferrite rod antenna?
LENGTH: a short phrase of about 2–5 words
ANSWER: insufficient information

* * *

CONTEXT: The best answer to the following question is drawn from A Primer of English Verse, a textbook published in 1892 by Hiram Corson, an American professor of literature.
QUESTION: What is the rhyme scheme in the sestet of the following sonnet?

Lawrence, of virtuous father virtuous son,
Now that the fields are dank, and ways are mire,
Where shall we sometimes meet, and by the fire
Help waste a sullen day, what may be won
From the hard season gaining? Time will run
On smoother, till Favonius reinspire
The frozen earth, and clothe in fresh attire
The lily and rose that neither sowed nor spun.
What neat repast shall feast us, light and choice,
Of Attic taste, with wine, whence we may rise
To hear the lute well touched, or artful voice
Warble immortal notes and Tuscan air?
He who of those delights can judge, and spare
To interpose them oft, is not unwise.
LENGTH: a few words
ANSWER: cdceed

* * *

CONTEXT: The following question is drawn from McCulloch's Universal Gazetteer, a gazetteer published in 1847 by J. R. McCulloch, a Scottish economist. Answers should be consistent with the knowledge likely contained in that volume.
QUESTION: What is the chief and only port of Japan?
LENGTH: a few words
ANSWER: Nangasaki

* * *

CONTEXT: The following question asks for information from an American encyclopedia published in 1897; your answer should reflect the state of knowledge and style of exposition current at the time.
QUESTION: What is the name of the hall at Persepolis that is described as the largest and most magnificent structure?
LENGTH: a short phrase of about 2–4 words
ANSWER:
```
