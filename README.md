# Hiss Byte Notation

Library to make it easy to use python literal syntax as a data format

Have you seen people try to print a dict and then use the JSON library to parse the output? This library is some
helper function for that scenario. It is a small wrapper around ast.literal_eval and will have a API similar to other
serializer/deserializers such as json, pickle, pyyaml, etc.

## Safety

`ast.literal_eval` is safer than `eval` but the python docs still imply that there are malicious payloads. I'm not
sure if they are the same problems that could affect json or other formats.

## Usage

```python
import hissbytenotation as hbn

data = {
    "mammal": "cat",
    "reptile": ["snake", "lizard"],
    "version": 1
}
data_as_string = hbn.dumps(data)

rehydrated = hbn.loads(data_as_string)
print(rehydrated)
# {'mammal': 'cat', 'reptile': ['snake', 'lizard'], 'version': 1}
```

## How it works

Serialization is done by calling repr, checking if ast.literal_eval can read it. Repr can be called on more data
structures than ast.literal_eval can handle.

Because ast.literal_eval is so slow, there are other options for deserialization:

- default: ast.literal_eval with validation enabled. Very slow, very safe.
- eval. Slow, only for trusted data.
- exec. Slow, only for trusted data.
- import. Two times faster than exec, only for trusted data.

## Serialization and deserialization times for 10,000 dumps/loads

    Pickle:  0.89 seconds
    JSON: 2.00 seconds
    HBN (no validation): 20.80 seconds
    HBN (validation): 40.57 seconds
    HBN (unsafe): 15.95 seconds
    HBN (exec): 18.08 seconds
    HBN (by import): 12.26 seconds

## Prior art

- [literal-python-to-pickle](https://github.com/albertz/literal-python-to-pickle) A faster replacement for
  ast.literal_eval and
  corresponding [question on stackoverflow](https://stackoverflow.com/questions/66480073/fastest-implementation-of-ast-literal-eval).

- You could just call `repr` and `ast.literal_eval` directly.

Possibly [astor](https://pypi.org/project/astor/) which serializes to a string representation of the AST, which looks
nothing like the source code, nor json.