IMPROVE CODE REGIONS

Let's add short/meaningful code regions to show structure of the code in simple way.

I like these generic regions like (examples):
- Init - for constructors / initialization
- Main - main functionality / main API / set of public methods
- Utilities (or Convenience) - extra functions providing some increased comfort / convenience for specific operations
- Internal - for internal methods (not part of public API)
- Properties - for all public properties
- Magic - for all magic methods like __str__ , __repr__, ...

But feel free to suggest any new apropriate and clear name for code region, that makes really sense
and creates logical, cohesive unit of functionality. So adapt to the content of each file.


Not all regions have to be used. Use only those, which are relevant.

Remove all empty regions.

Keep one empty line:
- after start of region `# region NAME`
- before end of region `# endregion`

Organize the order of functions in individual code regions in meaningful and logical way:
- more important functions first, less important later


---

IMPROVE ATTRIBUTE NAMES

Would it be possible to make the names of some attributes or variables more clear / intuitive / descriptive,
but still keep them short and concise (if possible, as intuitiveness is most important).
Do it only for files in attachment.

---

ADHERE TO JUNIE GUIDELINES

Go over each rule(s) and requirement(s) in Junie guidelines
and verify, if attached code file meet all required criteria
