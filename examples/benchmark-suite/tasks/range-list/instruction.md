Implement `compress(numbers)` and `expand(text)` in `/app/ranges.py`. The only other file is a
small visible test, `/app/test_ranges.py`.

Both use one text format, for example `"1-3,5,7-9"`:

- An integer is an optional `-` followed by one or more digits.
- Digits are the ASCII characters `0` to `9` only.
- The first digit is `0` only when it is the only digit, and zero is written without a `-`.
- An item is one integer, or a range `first-last` of two integers that stands for every integer
  from first to last inclusive.
- In a range, the first integer must be less than the last.
- Items are separated by `,`.

`compress(numbers)` takes any iterable of ints (list, set, generator, ...) and returns the text:

- It covers each distinct value once, in ascending order, whatever the input's order or repeats.
- Each maximal run of three or more consecutive values becomes one range. Every other value is
  written as its own item.
- The text has no spaces. An input with no values gives `""`.

`expand(text)` returns the list of ints that the text stands for:

- The list follows the order of the items: it is not sorted and repeats are kept.
- Any number of spaces may follow a comma, before the next item. A space anywhere else is malformed.
- No character may come before the first item or after the last item.
- The empty string gives `[]`.
- Raise `ValueError` for malformed text: anything that does not fit the format, e.g. an empty item.
