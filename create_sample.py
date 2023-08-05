import hissbytenotation as hbn

# with open("data.py", "w") as file:
#     file.write(hbn.dumps(generate_test_data()))

data = {"mammal": "cat", "reptile": ["snake", "lizard"], "version": 1}
data_as_string = hbn.dumps(data)

rehydrated = hbn.loads(data_as_string)
print(rehydrated)
# {'mammal': 'cat', 'reptile': ['snake', 'lizard'], 'version': 1}
