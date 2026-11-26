# Q107 — character_modeling (book_context)

Pool `character_modeling`; 9 eligible; k = 3 (requested 3); projected 1385/2048; fallback False. Answer cap (max_new_tokens) 60, same as zero-shot.

| | type | source | author |
|---|---|---|---|
| exemplar Q880 | character_modeling | `hvd.hn1sjm` | James Graham |
| exemplar Q645 | character_modeling | `hvd.32044082646845` | W. C. Scully |
| exemplar Q86 | character_modeling | `hvd.hnnwy1` | Shan F. Bullock |
| **target Q107** | character_modeling | `hvd.hw2bq6` | Carrie M. W. Willard |

Ground truth (not shown to model): 'I have cut the thongs from Sha-hehe. Cover her and heal her, old woman, against the time I come again. I shall want her then.'

## 1. Zero-shot, as the pipeline sends it today

**system**

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer in two to three sentences, about 10–30 words total.
```

**user**

```text
CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel with ethnographic elements published in 1892 by Carrie M. W. Willard, a American writer born in 1853.
QUESTION: The character in question here is Yealh-neddy, who is described this way in the book:
"Yealh-neddy is easily pleased, but hard to satisfy.", "Yealh-neddy was more than ever arrogant, and more than once the light from his evil eyes seemed to smite the girl."

At one moment in the book, Yealh-neddy loudly declares he has cut the thongs from Sha‑hehe and requests her healing as the boat departs. Write a short passage of dialogue (1-3 sentences) that Yealh-neddy might speak in this situation:
ANSWER: 
```

## 2. Few-shot, chat (OpenAI / OpenRouter / HF-instruct)

**system**

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.
```

**user**

```text
CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a adventure story published in 1927 by James Graham, a American writer born in 1891.
QUESTION: The character in question here is Ingram, who is described this way in the book:
"Ingram's black hair was cut short, and he wore no powder. His clothing was that of a gentleman of fashion; yet instead of a small sword, a heavy cutlass swung from a broad belt slanting across his body. His straight black brows drew together, his bold black eyes fixed themselves on the landlord's face.", "Wearing a French hat, blue-satin clothes, and silk stockings."

At one moment in the book, Ingram easily disarms a lieutenant in a brawl, drawing the attention of Captain Dale and the arrival of the watch. Write a short passage of dialogue (1-3 sentences) that Ingram might speak in this situation:
LENGTH: two to three sentences, about 20–30 words total
ANSWER:
```

**assistant**

```text
You hold your sword like a tailor. I always believed that the proper handling of arms was taught in his majesty's navy. I see that I have been misinformed.
```

**user**

```text
CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel published in 1898 by W. C. Scully, a South African writer born in 1855.
QUESTION: The character in question here is Elsie, who is described this way in the book:
"Her hair hung below her waist in a rich, yellow mass, and her eyes gleamed as they always did under the influence of excitement, and in appropriate light.", "She was now twelve years of age. Her stature and features were those of a very young child. With her pallid and spiritual countenance, and her yellow hair hanging in a thick mass below her waist, the blind girl with the wonderful eyes startled and impressed all who saw her, and seemed, in her rugged surroundings, like a being from another world.", "The blind child's face was paler and more set than usual, and the lustre of her eyes was like red, molten gold.", "Elsie did not speak, but her face lit up and her eyes flashed with almost unearthly gleams.", "poor little blind child", "Elsie was a silent child and possessed a calm and happy nature."

At one moment in the book, Elsie informs Gideon that her mother is dying and urges him to go. Write a short passage of dialogue (1-3 sentences) that Elsie might speak in this situation:
LENGTH: two to three sentences, about 5–30 words total
ANSWER:
```

**assistant**

```text
Uncle Gideon, my mother bids me tell you that she is dying, and that you must come to her at once.
```

**user**

```text
CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel published in 1899 by Shan F. Bullock, a Irish writer born in 1865.
QUESTION: The character in question here is John Butler, who is described this way in the book:
"He was a big man, with a square, ruddy face; the mouth large and mobile, the chin weak and flabby. His eyes were bright and kindly, his nose large, his head crowned with a shock of brown hair.", "old John was asleep, chin on breast and his lips dribbling.", "big John, hands in pockets, shoulders slouched, hat on the back of his head; goes shambling along, without care or purpose, just lounging about in the sunshine", "His face shone red as a coal. His eyes flared.", "John's face was solemn; one hand gripped his pipe stem, the other swung limply to and fro.", "Ould John, still clutching his pipe, had fallen asleep.", "John was a big, soft-handed, blethering Irishman, one who wanted work yet loathed it, spoke one thing and meant the other, said he was this and looked that."

At one moment John observes two young people flirting, and comments indirectly on it.

Write a short passage of dialogue (1-3 sentences) that we might expect from John Butler:
LENGTH: two to three sentences, about 10–40 words total
ANSWER:
```

**assistant**

```text
Ay, ay. Love an' blarney, love that makes the world go round, an' blarney that keeps it goin. Ay, ay.
```

**user**

```text
CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel with ethnographic elements published in 1892 by Carrie M. W. Willard, a American writer born in 1853.
QUESTION: The character in question here is Yealh-neddy, who is described this way in the book:
"Yealh-neddy is easily pleased, but hard to satisfy.", "Yealh-neddy was more than ever arrogant, and more than once the light from his evil eyes seemed to smite the girl."

At one moment in the book, Yealh-neddy loudly declares he has cut the thongs from Sha‑hehe and requests her healing as the boat departs. Write a short passage of dialogue (1-3 sentences) that Yealh-neddy might speak in this situation:
LENGTH: two to three sentences, about 10–30 words total
ANSWER:
```

## 3. Few-shot, Talkie-IT literal string

1270 reference tokens. 

```text
<|system|>Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.<|end|><|user|>CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a adventure story published in 1927 by James Graham, a American writer born in 1891.
QUESTION: The character in question here is Ingram, who is described this way in the book:
"Ingram's black hair was cut short, and he wore no powder. His clothing was that of a gentleman of fashion; yet instead of a small sword, a heavy cutlass swung from a broad belt slanting across his body. His straight black brows drew together, his bold black eyes fixed themselves on the landlord's face.", "Wearing a French hat, blue-satin clothes, and silk stockings."

At one moment in the book, Ingram easily disarms a lieutenant in a brawl, drawing the attention of Captain Dale and the arrival of the watch. Write a short passage of dialogue (1-3 sentences) that Ingram might speak in this situation:
LENGTH: two to three sentences, about 20–30 words total
ANSWER:<|end|><|assistant|>You hold your sword like a tailor. I always believed that the proper handling of arms was taught in his majesty's navy. I see that I have been misinformed.<|end|><|user|>CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel published in 1898 by W. C. Scully, a South African writer born in 1855.
QUESTION: The character in question here is Elsie, who is described this way in the book:
"Her hair hung below her waist in a rich, yellow mass, and her eyes gleamed as they always did under the influence of excitement, and in appropriate light.", "She was now twelve years of age. Her stature and features were those of a very young child. With her pallid and spiritual countenance, and her yellow hair hanging in a thick mass below her waist, the blind girl with the wonderful eyes startled and impressed all who saw her, and seemed, in her rugged surroundings, like a being from another world.", "The blind child's face was paler and more set than usual, and the lustre of her eyes was like red, molten gold.", "Elsie did not speak, but her face lit up and her eyes flashed with almost unearthly gleams.", "poor little blind child", "Elsie was a silent child and possessed a calm and happy nature."

At one moment in the book, Elsie informs Gideon that her mother is dying and urges him to go. Write a short passage of dialogue (1-3 sentences) that Elsie might speak in this situation:
LENGTH: two to three sentences, about 5–30 words total
ANSWER:<|end|><|assistant|>Uncle Gideon, my mother bids me tell you that she is dying, and that you must come to her at once.<|end|><|user|>CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel published in 1899 by Shan F. Bullock, a Irish writer born in 1865.
QUESTION: The character in question here is John Butler, who is described this way in the book:
"He was a big man, with a square, ruddy face; the mouth large and mobile, the chin weak and flabby. His eyes were bright and kindly, his nose large, his head crowned with a shock of brown hair.", "old John was asleep, chin on breast and his lips dribbling.", "big John, hands in pockets, shoulders slouched, hat on the back of his head; goes shambling along, without care or purpose, just lounging about in the sunshine", "His face shone red as a coal. His eyes flared.", "John's face was solemn; one hand gripped his pipe stem, the other swung limply to and fro.", "Ould John, still clutching his pipe, had fallen asleep.", "John was a big, soft-handed, blethering Irishman, one who wanted work yet loathed it, spoke one thing and meant the other, said he was this and looked that."

At one moment John observes two young people flirting, and comments indirectly on it.

Write a short passage of dialogue (1-3 sentences) that we might expect from John Butler:
LENGTH: two to three sentences, about 10–40 words total
ANSWER:<|end|><|assistant|>Ay, ay. Love an' blarney, love that makes the world go round, an' blarney that keeps it goin. Ay, ay.<|end|><|user|>CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel with ethnographic elements published in 1892 by Carrie M. W. Willard, a American writer born in 1853.
QUESTION: The character in question here is Yealh-neddy, who is described this way in the book:
"Yealh-neddy is easily pleased, but hard to satisfy.", "Yealh-neddy was more than ever arrogant, and more than once the light from his evil eyes seemed to smite the girl."

At one moment in the book, Yealh-neddy loudly declares he has cut the thongs from Sha‑hehe and requests her healing as the boat departs. Write a short passage of dialogue (1-3 sentences) that Yealh-neddy might speak in this situation:
LENGTH: two to three sentences, about 10–30 words total
ANSWER:<|end|><|assistant|>
```

## 4. Few-shot, completion (Talkie-base, HF base models)

1227 reference tokens. Stop strings: `'\n* * *'`, `'\nCONTEXT:'`, `'<|endoftext|>'`, `'<|end|>'`, `'<|user|>'`.

```text
Answer the question in a way that fits the beliefs and expository style of the historical context described. As a rough guideline, answer at the length given with each question. The questions before the last are worked examples drawn from other books and periods: follow their form, but answer the final question from its own context.

* * *

CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a adventure story published in 1927 by James Graham, a American writer born in 1891.
QUESTION: The character in question here is Ingram, who is described this way in the book:
"Ingram's black hair was cut short, and he wore no powder. His clothing was that of a gentleman of fashion; yet instead of a small sword, a heavy cutlass swung from a broad belt slanting across his body. His straight black brows drew together, his bold black eyes fixed themselves on the landlord's face.", "Wearing a French hat, blue-satin clothes, and silk stockings."

At one moment in the book, Ingram easily disarms a lieutenant in a brawl, drawing the attention of Captain Dale and the arrival of the watch. Write a short passage of dialogue (1-3 sentences) that Ingram might speak in this situation:
LENGTH: two to three sentences, about 20–30 words total
ANSWER: You hold your sword like a tailor. I always believed that the proper handling of arms was taught in his majesty's navy. I see that I have been misinformed.

* * *

CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel published in 1898 by W. C. Scully, a South African writer born in 1855.
QUESTION: The character in question here is Elsie, who is described this way in the book:
"Her hair hung below her waist in a rich, yellow mass, and her eyes gleamed as they always did under the influence of excitement, and in appropriate light.", "She was now twelve years of age. Her stature and features were those of a very young child. With her pallid and spiritual countenance, and her yellow hair hanging in a thick mass below her waist, the blind girl with the wonderful eyes startled and impressed all who saw her, and seemed, in her rugged surroundings, like a being from another world.", "The blind child's face was paler and more set than usual, and the lustre of her eyes was like red, molten gold.", "Elsie did not speak, but her face lit up and her eyes flashed with almost unearthly gleams.", "poor little blind child", "Elsie was a silent child and possessed a calm and happy nature."

At one moment in the book, Elsie informs Gideon that her mother is dying and urges him to go. Write a short passage of dialogue (1-3 sentences) that Elsie might speak in this situation:
LENGTH: two to three sentences, about 5–30 words total
ANSWER: Uncle Gideon, my mother bids me tell you that she is dying, and that you must come to her at once.

* * *

CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel published in 1899 by Shan F. Bullock, a Irish writer born in 1865.
QUESTION: The character in question here is John Butler, who is described this way in the book:
"He was a big man, with a square, ruddy face; the mouth large and mobile, the chin weak and flabby. His eyes were bright and kindly, his nose large, his head crowned with a shock of brown hair.", "old John was asleep, chin on breast and his lips dribbling.", "big John, hands in pockets, shoulders slouched, hat on the back of his head; goes shambling along, without care or purpose, just lounging about in the sunshine", "His face shone red as a coal. His eyes flared.", "John's face was solemn; one hand gripped his pipe stem, the other swung limply to and fro.", "Ould John, still clutching his pipe, had fallen asleep.", "John was a big, soft-handed, blethering Irishman, one who wanted work yet loathed it, spoke one thing and meant the other, said he was this and looked that."

At one moment John observes two young people flirting, and comments indirectly on it.

Write a short passage of dialogue (1-3 sentences) that we might expect from John Butler:
LENGTH: two to three sentences, about 10–40 words total
ANSWER: Ay, ay. Love an' blarney, love that makes the world go round, an' blarney that keeps it goin. Ay, ay.

* * *

CONTEXT: This question asks you to provide dialogue for a character in a book. The book in this case is a novel with ethnographic elements published in 1892 by Carrie M. W. Willard, a American writer born in 1853.
QUESTION: The character in question here is Yealh-neddy, who is described this way in the book:
"Yealh-neddy is easily pleased, but hard to satisfy.", "Yealh-neddy was more than ever arrogant, and more than once the light from his evil eyes seemed to smite the girl."

At one moment in the book, Yealh-neddy loudly declares he has cut the thongs from Sha‑hehe and requests her healing as the boat departs. Write a short passage of dialogue (1-3 sentences) that Yealh-neddy might speak in this situation:
LENGTH: two to three sentences, about 10–30 words total
ANSWER:
```
