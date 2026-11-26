# Q269 — phrase_cloze (passage_context)

Pool `phrase_cloze`; 17 eligible; k = 3 (requested 3); projected 1038/2048; fallback False. Answer cap (max_new_tokens) 40, same as zero-shot.

| | type | source | author |
|---|---|---|---|
| exemplar Q154 | phrase_cloze | `hvd.32044038429635` | Henry Van Dyke |
| exemplar Q224 | phrase_cloze | `hvd.hxdnai` | William A. Quayle |
| exemplar Q667 | phrase_cloze | `hvd.32044004506143` | O. W. Wahl |
| **target Q269** | phrase_cloze | `hvd.32044037714573` | William Burnet Wright |

Ground truth (not shown to model): 'so that eventually every revelation made in Greek came with wings'

## 1. Zero-shot, as the pipeline sends it today

**system**

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer in one phrase of about 5–20 words.
```

**user**

```text
CONTEXT: The following passage comes from Ancient Cities From the Dawn to the Daylight, a historical study published in 1886 by William Burnet Wright, an American Congregational clergyman.
QUESTION: The Greek tongue excels all other tongues, as Greek art transcends all other art. A sentiment was generated and diffused which counted mental more precious than material riches, and realized that a man's life consists not in the abundance of the things he possesses, but in that which he is. Because they were mentally the ablest, the most cultivated, and in all powers of expression, whether music, art, or speech, immeasurably the most gifted of mankind, the Greeks naturally became the teachers of the race, [missing clause describing an inference or effect]. The religion of Israel, which had limped in Hebrew, flew when it was translated into Greek.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing an inference or effect]:
ANSWER: 
```

## 2. Few-shot, chat (OpenAI / OpenRouter / HF-instruct)

**system**

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.
```

**user**

```text
CONTEXT: The following passage comes from Counsels By the Way, a book of essays published in 1897 by Henry Van Dyke, an American diplomat and Presbyterian clergyman.
QUESTION: It is not in the least vague. It is only free; it has the power to embody itself in a thousand forms without changing its character. Those who seek it know what it means, however it may be expressed. It is real and genuine and satisfying. There is nothing beyond it, [missing clause describing a cause or reason]. It is the translation, through many languages, of the true, divine purpose of all the work and labour that is done beneath the sun, into one final, universal word.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing a cause or reason]:
LENGTH: one phrase of about 10–20 words
ANSWER:
```

**assistant**

```text
because there can be no higher practical result of effort
```

**user**

```text
CONTEXT: The following passage comes from The Poet's Poet and Other Essays, a book of essays published in 1897 by William A. Quayle, an American bishop of the Methodist church.
QUESTION: Love of truth, country, river, cushat, mousie, daisy, lassie (be she Mary, Eliza, or Jean),—that was 

Burns's literary biography. Love means melancholy; and it is quite beyond credence persistently shadows hang over all Burns wrote, until you take his poems and go over them at a sitting. Rollicking he seems to be, [missing clause describing a tension or contrast]. The fear of parting is on his meeting with Mary.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing a tension or contrast]:
LENGTH: one phrase of about 5–20 words
ANSWER:
```

**assistant**

```text
but sad at heart you will always find him
```

**user**

```text
CONTEXT: The following passage comes from The Land of the Czar, an ethnology published in 1875 by O. W. Wahl.
QUESTION: In 1632 he opened another campaign against Poland, in consequence of which he lost all former conquests, and had to give up all claims on Livonia, Esthonia, and Courland; but, on the other hand, the Poles formally abandoned their claims to the Russian throne. He signed also a treaty with the Grand Sultan, by which the latter promised to prevent the Khan of the Crimea from any renewed invasions of the Russian territories. Michael proved himself to have been a most able politician, and considerably added to the extension of the empire, [missing clause describing an inference or effect]. He died in the year 1646.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing an inference or effect]:
LENGTH: one sentence of about 10–30 words
ANSWER:
```

**assistant**

```text
so that at his death his own son saw himself master of a country not less than 255,000 square miles in extent
```

**user**

```text
CONTEXT: The following passage comes from Ancient Cities From the Dawn to the Daylight, a historical study published in 1886 by William Burnet Wright, an American Congregational clergyman.
QUESTION: The Greek tongue excels all other tongues, as Greek art transcends all other art. A sentiment was generated and diffused which counted mental more precious than material riches, and realized that a man's life consists not in the abundance of the things he possesses, but in that which he is. Because they were mentally the ablest, the most cultivated, and in all powers of expression, whether music, art, or speech, immeasurably the most gifted of mankind, the Greeks naturally became the teachers of the race, [missing clause describing an inference or effect]. The religion of Israel, which had limped in Hebrew, flew when it was translated into Greek.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing an inference or effect]:
LENGTH: one phrase of about 5–20 words
ANSWER:
```

## 3. Few-shot, Talkie-IT literal string

949 reference tokens. 

```text
<|system|>Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.<|end|><|user|>CONTEXT: The following passage comes from Counsels By the Way, a book of essays published in 1897 by Henry Van Dyke, an American diplomat and Presbyterian clergyman.
QUESTION: It is not in the least vague. It is only free; it has the power to embody itself in a thousand forms without changing its character. Those who seek it know what it means, however it may be expressed. It is real and genuine and satisfying. There is nothing beyond it, [missing clause describing a cause or reason]. It is the translation, through many languages, of the true, divine purpose of all the work and labour that is done beneath the sun, into one final, universal word.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing a cause or reason]:
LENGTH: one phrase of about 10–20 words
ANSWER:<|end|><|assistant|>because there can be no higher practical result of effort<|end|><|user|>CONTEXT: The following passage comes from The Poet's Poet and Other Essays, a book of essays published in 1897 by William A. Quayle, an American bishop of the Methodist church.
QUESTION: Love of truth, country, river, cushat, mousie, daisy, lassie (be she Mary, Eliza, or Jean),—that was 

Burns's literary biography. Love means melancholy; and it is quite beyond credence persistently shadows hang over all Burns wrote, until you take his poems and go over them at a sitting. Rollicking he seems to be, [missing clause describing a tension or contrast]. The fear of parting is on his meeting with Mary.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing a tension or contrast]:
LENGTH: one phrase of about 5–20 words
ANSWER:<|end|><|assistant|>but sad at heart you will always find him<|end|><|user|>CONTEXT: The following passage comes from The Land of the Czar, an ethnology published in 1875 by O. W. Wahl.
QUESTION: In 1632 he opened another campaign against Poland, in consequence of which he lost all former conquests, and had to give up all claims on Livonia, Esthonia, and Courland; but, on the other hand, the Poles formally abandoned their claims to the Russian throne. He signed also a treaty with the Grand Sultan, by which the latter promised to prevent the Khan of the Crimea from any renewed invasions of the Russian territories. Michael proved himself to have been a most able politician, and considerably added to the extension of the empire, [missing clause describing an inference or effect]. He died in the year 1646.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing an inference or effect]:
LENGTH: one sentence of about 10–30 words
ANSWER:<|end|><|assistant|>so that at his death his own son saw himself master of a country not less than 255,000 square miles in extent<|end|><|user|>CONTEXT: The following passage comes from Ancient Cities From the Dawn to the Daylight, a historical study published in 1886 by William Burnet Wright, an American Congregational clergyman.
QUESTION: The Greek tongue excels all other tongues, as Greek art transcends all other art. A sentiment was generated and diffused which counted mental more precious than material riches, and realized that a man's life consists not in the abundance of the things he possesses, but in that which he is. Because they were mentally the ablest, the most cultivated, and in all powers of expression, whether music, art, or speech, immeasurably the most gifted of mankind, the Greeks naturally became the teachers of the race, [missing clause describing an inference or effect]. The religion of Israel, which had limped in Hebrew, flew when it was translated into Greek.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing an inference or effect]:
LENGTH: one phrase of about 5–20 words
ANSWER:<|end|><|assistant|>
```

## 4. Few-shot, completion (Talkie-base, HF base models)

909 reference tokens. Stop strings: `'\n* * *'`, `'\nCONTEXT:'`, `'<|endoftext|>'`, `'<|end|>'`, `'<|user|>'`.

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.

* * *

CONTEXT: The following passage comes from Counsels By the Way, a book of essays published in 1897 by Henry Van Dyke, an American diplomat and Presbyterian clergyman.
QUESTION: It is not in the least vague. It is only free; it has the power to embody itself in a thousand forms without changing its character. Those who seek it know what it means, however it may be expressed. It is real and genuine and satisfying. There is nothing beyond it, [missing clause describing a cause or reason]. It is the translation, through many languages, of the true, divine purpose of all the work and labour that is done beneath the sun, into one final, universal word.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing a cause or reason]:
LENGTH: one phrase of about 10–20 words
ANSWER: because there can be no higher practical result of effort

* * *

CONTEXT: The following passage comes from The Poet's Poet and Other Essays, a book of essays published in 1897 by William A. Quayle, an American bishop of the Methodist church.
QUESTION: Love of truth, country, river, cushat, mousie, daisy, lassie (be she Mary, Eliza, or Jean),—that was 

Burns's literary biography. Love means melancholy; and it is quite beyond credence persistently shadows hang over all Burns wrote, until you take his poems and go over them at a sitting. Rollicking he seems to be, [missing clause describing a tension or contrast]. The fear of parting is on his meeting with Mary.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing a tension or contrast]:
LENGTH: one phrase of about 5–20 words
ANSWER: but sad at heart you will always find him

* * *

CONTEXT: The following passage comes from The Land of the Czar, an ethnology published in 1875 by O. W. Wahl.
QUESTION: In 1632 he opened another campaign against Poland, in consequence of which he lost all former conquests, and had to give up all claims on Livonia, Esthonia, and Courland; but, on the other hand, the Poles formally abandoned their claims to the Russian throne. He signed also a treaty with the Grand Sultan, by which the latter promised to prevent the Khan of the Crimea from any renewed invasions of the Russian territories. Michael proved himself to have been a most able politician, and considerably added to the extension of the empire, [missing clause describing an inference or effect]. He died in the year 1646.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing an inference or effect]:
LENGTH: one sentence of about 10–30 words
ANSWER: so that at his death his own son saw himself master of a country not less than 255,000 square miles in extent

* * *

CONTEXT: The following passage comes from Ancient Cities From the Dawn to the Daylight, a historical study published in 1886 by William Burnet Wright, an American Congregational clergyman.
QUESTION: The Greek tongue excels all other tongues, as Greek art transcends all other art. A sentiment was generated and diffused which counted mental more precious than material riches, and realized that a man's life consists not in the abundance of the things he possesses, but in that which he is. Because they were mentally the ablest, the most cultivated, and in all powers of expression, whether music, art, or speech, immeasurably the most gifted of mankind, the Greeks naturally became the teachers of the race, [missing clause describing an inference or effect]. The religion of Israel, which had limped in Hebrew, flew when it was translated into Greek.

Write a clause appropriate for this book that could stand in the position marked by [missing clause describing an inference or effect]:
LENGTH: one phrase of about 5–20 words
ANSWER:
```
