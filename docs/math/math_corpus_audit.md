# Math corpus audit

- source root: `C:\Users\86184\Desktop\xinzhi-daoxue`
- Markdown files: `56`
- formula instances: `64316`
- protected fenced/inline code spans: `2`
- manifest rows observed: `3418`

## Formula counts

| delimiter | count |
| --- | ---: |
| `display` | 10814 |
| `inline` | 53502 |

## Risk counts

| risk | count |
| --- | ---: |
| `HIGH` | 317 |
| `LOW` | 59369 |
| `MEDIUM` | 4630 |

## Per-course counts

| course | Markdown | formulas | HIGH | MEDIUM | LOW |
| --- | ---: | ---: | ---: | ---: | ---: |
| `CT` | 16 | 11963 | 23 | 1322 | 10618 |
| `AE` | 11 | 11120 | 134 | 543 | 10443 |
| `DE` | 12 | 7598 | 32 | 388 | 7178 |
| `SS` | 2 | 13834 | 37 | 1011 | 12786 |
| `DSP` | 1 | 10242 | 42 | 865 | 9335 |
| `COMM` | 14 | 9559 | 49 | 501 | 9009 |

## Method and boundaries

The scanner tokenizes fenced code and inline backtick code before math. It only emits paired delimiters and never rewrites course sources. A HIGH risk item requires review before an actual KaTeX render claim; the report is structural and does not invent render results.
