# Q765 — constrained_generation (book_context)

Pool `constrained_generation`; 17 eligible; k = 3 (requested 3); projected 1095/2048; fallback False. Answer cap (max_new_tokens) 240, same as zero-shot.

| | type | source | author |
|---|---|---|---|
| exemplar Q723 | constrained_generation | `32044009690504` | Mrs (Sarah Stickney) Ellis |
| exemplar Q495 | constrained_generation | `32044102772175` | Martha Hale Shackford |
| exemplar Q424 | constrained_generation | `32044004376976` | Baman Das Basu |
| **target Q765** | constrained_generation | `AH6GGZ` |  |

Ground truth (not shown to model): 'The readers of the Review have been to a limited extent informed of the manner in which the officers of our government have been treating the Indians, but not a tenth of the inhuman, atrocious barbarities committed by the officers and soldiers of the government, and which are on file and record in the Indian Department in Washington, has been told them. The community have heard so much of war and bloodshed during the last few years that they have become callous to reports of outrage and cruelty which would have excited them under other circumstances; although they have heard but very little of the wholesale slaughter of hundreds of defenceless, innocent Indian women and children who were confiding in the protection of the very military forces by whom they were murdered.'

## 1. Zero-shot, as the pipeline sends it today

**system**

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer in three to five sentences, about 100–120 words total.
```

**user**

```text
CONTEXT: The following question is based on the 1868 volume of Friends' Review, a Quaker periodical published in Philadelphia. Good answers will approximate the likely perspective of that source.
QUESTION: Describe interactions between the US Government and Indian tribes toward the end of the 1860s.
ANSWER: 
```

## 2. Few-shot, chat (OpenAI / OpenRouter / HF-instruct)

**system**

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.
```

**user**

```text
CONTEXT: The best answers to the following question will echo the perspective of a volume about the moral responsibility of motherhood, published in 1844 by a British woman who was an educator and writer.
QUESTION: Should mothers exercise authority within the home?
LENGTH: two to three sentences, about 50–100 words total
ANSWER:
```

**assistant**

```text
It is just possible that there should be among women some of those stern, cold, commanding characters, to which authority, simply as such, appropriately belongs. If, however, authority belongs as a natural right to such characters, the finer and more vital elements of moral influence never can be theirs; and to imagine the tenderness of childhood committed to a mother of this description, is to call up a picture too revolting for the mind to dwell upon without shrinking and horror. Such a mother may possibly govern the actions of her children by the exercise of absolute power, but she can never know the sweet security of moral influence, which operates as effectually when distant and unseen, as when every act of youth is watched by the most scrutinizing eye.
```

**user**

```text
CONTEXT: The best answer to the following question is drawn from Composition, Rhetoric, Literature : a Four Year's Course for Secondary Schools, a textbook published in 1913 by Martha Hale Shackford, an American literary scholar.
QUESTION: Suppose that your name is Jennifer Lane, you're unmarried, and you've been invited to dinner. But you can't go or don't want to. Write a note declining the invitation.
LENGTH: three to five sentences, about 10–50 words total
ANSWER:
```

**assistant**

```text
Miss Lane regrets that a previous engagement prevents her from accepting Mrs. Irving's kind invitation to dinner on Tuesday, February fourth, at seven o'clock. 2 University Place, January thirty-first.
```

**user**

```text
CONTEXT: The following question is based on History of Education in India Under the Rule of the East India Company, a history published in 1922 by Baman Das Basu, an Indian physician, nationalist, and historian. The best answer will approximate Basu's likely response.
QUESTION: How central was Thomas Babington Macaulay to the emergence of Western education in India?
LENGTH: two to three sentences, about 30–50 words total
ANSWER:
```

**assistant**

```text
It should also not be lost sight of that the Indians themselves were the pioneers in introducing Western education in this country. The Hindu College of Calcutta was established long before Macaulay penned his celebrated minute or Wood sent out his Educational Despatch to India.
```

**user**

```text
CONTEXT: The following question is based on the 1868 volume of Friends' Review, a Quaker periodical published in Philadelphia. Good answers will approximate the likely perspective of that source.
QUESTION: Describe interactions between the US Government and Indian tribes toward the end of the 1860s.
LENGTH: three to five sentences, about 100–120 words total
ANSWER:
```

## 3. Few-shot, Talkie-IT literal string

710 reference tokens. 

```text
<|system|>Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.<|end|><|user|>CONTEXT: The best answers to the following question will echo the perspective of a volume about the moral responsibility of motherhood, published in 1844 by a British woman who was an educator and writer.
QUESTION: Should mothers exercise authority within the home?
LENGTH: two to three sentences, about 50–100 words total
ANSWER:<|end|><|assistant|>It is just possible that there should be among women some of those stern, cold, commanding characters, to which authority, simply as such, appropriately belongs. If, however, authority belongs as a natural right to such characters, the finer and more vital elements of moral influence never can be theirs; and to imagine the tenderness of childhood committed to a mother of this description, is to call up a picture too revolting for the mind to dwell upon without shrinking and horror. Such a mother may possibly govern the actions of her children by the exercise of absolute power, but she can never know the sweet security of moral influence, which operates as effectually when distant and unseen, as when every act of youth is watched by the most scrutinizing eye.<|end|><|user|>CONTEXT: The best answer to the following question is drawn from Composition, Rhetoric, Literature : a Four Year's Course for Secondary Schools, a textbook published in 1913 by Martha Hale Shackford, an American literary scholar.
QUESTION: Suppose that your name is Jennifer Lane, you're unmarried, and you've been invited to dinner. But you can't go or don't want to. Write a note declining the invitation.
LENGTH: three to five sentences, about 10–50 words total
ANSWER:<|end|><|assistant|>Miss Lane regrets that a previous engagement prevents her from accepting Mrs. Irving's kind invitation to dinner on Tuesday, February fourth, at seven o'clock. 2 University Place, January thirty-first.<|end|><|user|>CONTEXT: The following question is based on History of Education in India Under the Rule of the East India Company, a history published in 1922 by Baman Das Basu, an Indian physician, nationalist, and historian. The best answer will approximate Basu's likely response.
QUESTION: How central was Thomas Babington Macaulay to the emergence of Western education in India?
LENGTH: two to three sentences, about 30–50 words total
ANSWER:<|end|><|assistant|>It should also not be lost sight of that the Indians themselves were the pioneers in introducing Western education in this country. The Hindu College of Calcutta was established long before Macaulay penned his celebrated minute or Wood sent out his Educational Despatch to India.<|end|><|user|>CONTEXT: The following question is based on the 1868 volume of Friends' Review, a Quaker periodical published in Philadelphia. Good answers will approximate the likely perspective of that source.
QUESTION: Describe interactions between the US Government and Indian tribes toward the end of the 1860s.
LENGTH: three to five sentences, about 100–120 words total
ANSWER:<|end|><|assistant|>
```

## 4. Few-shot, completion (Talkie-base, HF base models)

667 reference tokens. Stop strings: `'\n* * *'`, `'\nCONTEXT:'`, `'<|endoftext|>'`, `'<|end|>'`, `'<|user|>'`.

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.

* * *

CONTEXT: The best answers to the following question will echo the perspective of a volume about the moral responsibility of motherhood, published in 1844 by a British woman who was an educator and writer.
QUESTION: Should mothers exercise authority within the home?
LENGTH: two to three sentences, about 50–100 words total
ANSWER: It is just possible that there should be among women some of those stern, cold, commanding characters, to which authority, simply as such, appropriately belongs. If, however, authority belongs as a natural right to such characters, the finer and more vital elements of moral influence never can be theirs; and to imagine the tenderness of childhood committed to a mother of this description, is to call up a picture too revolting for the mind to dwell upon without shrinking and horror. Such a mother may possibly govern the actions of her children by the exercise of absolute power, but she can never know the sweet security of moral influence, which operates as effectually when distant and unseen, as when every act of youth is watched by the most scrutinizing eye.

* * *

CONTEXT: The best answer to the following question is drawn from Composition, Rhetoric, Literature : a Four Year's Course for Secondary Schools, a textbook published in 1913 by Martha Hale Shackford, an American literary scholar.
QUESTION: Suppose that your name is Jennifer Lane, you're unmarried, and you've been invited to dinner. But you can't go or don't want to. Write a note declining the invitation.
LENGTH: three to five sentences, about 10–50 words total
ANSWER: Miss Lane regrets that a previous engagement prevents her from accepting Mrs. Irving's kind invitation to dinner on Tuesday, February fourth, at seven o'clock. 2 University Place, January thirty-first.

* * *

CONTEXT: The following question is based on History of Education in India Under the Rule of the East India Company, a history published in 1922 by Baman Das Basu, an Indian physician, nationalist, and historian. The best answer will approximate Basu's likely response.
QUESTION: How central was Thomas Babington Macaulay to the emergence of Western education in India?
LENGTH: two to three sentences, about 30–50 words total
ANSWER: It should also not be lost sight of that the Indians themselves were the pioneers in introducing Western education in this country. The Hindu College of Calcutta was established long before Macaulay penned his celebrated minute or Wood sent out his Educational Despatch to India.

* * *

CONTEXT: The following question is based on the 1868 volume of Friends' Review, a Quaker periodical published in Philadelphia. Good answers will approximate the likely perspective of that source.
QUESTION: Describe interactions between the US Government and Indian tribes toward the end of the 1860s.
LENGTH: three to five sentences, about 100–120 words total
ANSWER:
```
