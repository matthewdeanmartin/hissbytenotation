import timeit
import pickle
import json
import yaml
import hissbytenotation as hbn
import test.generate as generator

data = generator.generate_test_data(no_bytes=True, no_sets=True, no_elipsis=True)


def benchmark_hbn_no_validate_unsafe():
    hbn.dumps(data, validate=False)
    # deserialized = hbn.loads(serialized, unsafe=True)


def benchmark_hbn_no_validate():
    hbn.dumps(data, validate=False)
    # deserialized = hbn.loads(serialized)


def benchmark_hbn_validate():
    hbn.dumps(data, validate=True)
    # deserialized = hbn.loads(serialized)


def benchmark_pickle():
    pickle.dumps(data)
    # deserialized = pickle.loads(serialized)


def benchmark_json():
    json.dumps(data)
    # deserialized = json.loads(serialized)


def benchmark_yaml():
    # try:
    yaml.dump(data, default_flow_style=False)
    # except Exception as E:
    #     raise E

    # deserialized = yaml.load(serialized, Loader=yaml.FullLoader)


pickle_time = timeit.timeit(benchmark_pickle, number=10000)
json_time = timeit.timeit(benchmark_json, number=10000)
# can't represent a lot?
# yaml_time = timeit.timeit(benchmark_yaml, number=10000)
hbn_time_no_validate = timeit.timeit(benchmark_hbn_no_validate, number=10000)
hbn_time_validate = timeit.timeit(benchmark_hbn_validate, number=10000)
hbn_time_unsafe = timeit.timeit(benchmark_hbn_no_validate_unsafe, number=10000)

print(f"Pickle serialization and deserialization time: {pickle_time:.6f} seconds")
print(f"JSON serialization and deserialization time: {json_time:.6f} seconds")
# print(f"YAML serialization and deserialization time: {yaml_time:.6f} seconds")
print(f"HBN serialization and deserialization time (no validation): {hbn_time_no_validate:.6f} seconds")
print(f"HBN serialization and deserialization time (validation): {hbn_time_validate:.6f} seconds")
print(f"HBN serialization and deserialization time (unsafe): {hbn_time_unsafe:.6f} seconds")
