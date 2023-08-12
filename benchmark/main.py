import timeit
import pickle
import json
import yaml
import hissbytenotation as hbn
import test.generate as generator

data = generator.generate_test_data(no_bytes=True, no_sets=True, no_elipsis=True)


def benchmark_hbn_no_validate_exec():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized, by_exec=True)


def benchmark_hbn_no_validate_by_import():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized, by_import=True)


def benchmark_hbn_no_validate_by_eval():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized, by_eval=True)


def benchmark_hbn_no_validate():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized)


def benchmark_hbn_validate():
    serialized = hbn.dumps(data, validate=True)
    hbn.loads(serialized)


def benchmark_pickle():
    serialized = pickle.dumps(data)
    pickle.loads(serialized)


def benchmark_json():
    serialized = json.dumps(data)
    json.loads(serialized)


def benchmark_yaml():
    # try:
    serialized = yaml.dump(data, default_flow_style=False)
    # except Exception as E:
    #     raise E

    yaml.load(serialized, Loader=yaml.FullLoader)


pickle_time = timeit.timeit(benchmark_pickle, number=10000)
json_time = timeit.timeit(benchmark_json, number=10000)
# can't represent a lot?
# yaml_time = timeit.timeit(benchmark_yaml, number=10000)
hbn_time_no_validate = timeit.timeit(benchmark_hbn_no_validate, number=10000)
hbn_time_validate = timeit.timeit(benchmark_hbn_validate, number=10000)
hbn_time_by_eval = timeit.timeit(benchmark_hbn_no_validate_by_eval, number=10000)
hbn_time_exec = timeit.timeit(benchmark_hbn_no_validate_exec, number=10000)
hbn_time_by_import = timeit.timeit(benchmark_hbn_no_validate_by_import, number=10000)

print("## Serialization and deserialization times for 10,000 dumps/loads")
print(f"Pickle:  {pickle_time:.6f} seconds")
print(f"JSON: {json_time:.6f} seconds")
# print(f"YAML serialization and deserialization time: {yaml_time:.6f} seconds")
print(f"HBN (no validation): {hbn_time_no_validate:.6f} seconds")
print(f"HBN (validation): {hbn_time_validate:.6f} seconds")
print(f"HBN (eval): {hbn_time_by_eval:.6f} seconds")
print(f"HBN (exec): {hbn_time_exec:.6f} seconds")
print(f"HBN (by import): {hbn_time_by_import:.6f} seconds")
