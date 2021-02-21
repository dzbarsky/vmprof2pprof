import gzip
import sys
import vmprof

from profile_pb2 import Line, Function, Location, Sample, Profile, ValueType

FunctionId = int

def fq_function_name(filename, fn_name):
    parts = filename.split('/')
    try:
        parts = parts[parts.index('site-packages') + 1:]
    except ValueError:
        pass
    return fn_name + ":" + '.'.join(parts)

class ProfileBuilder:
    def __init__(self):
        self._functions_mapping: Dict[Tuple[str, int], int] = {}
        self._functions: List[Function] = []

        self._locations_mapping: Dict[Tuple[FunctionId, int], int] = {}
        self._locations: List[Location] = []

        self._samples: List[Sample] = []

        self._strings = [""]
        self._string_table = {"": 0}

    def string(self, s: str) -> int:
        i = self._string_table.get(s)
        if i is None:
            i = len(self._strings)
            self._string_table[s] = i
            self._strings.append(s)
        return i

    def function_id(self, funcname: str, filename: str, line: int):
        key = (filename, line)
        function_id = self._functions_mapping.get(key)
        if not function_id:
            function_id = len(self._functions) + 1
            function = Function(
                id = function_id,
                name = self.string(funcname),
                filename = self.string(filename),
                start_line = line,
            )
            self._functions.append(function)
            self._functions_mapping[key] = function_id
        return function_id

    def location_id(self, function_id: FunctionId, line: int) -> int:
        key = (function_id, line)
        location_id = self._locations_mapping.get(key)
        if location_id is None:
            location_id = len(self._locations) + 1
            location = Location(
                id = location_id,
                line = [Line(function_id = function_id, line = line)],
            )
            self._locations.append(location)
            self._locations_mapping[key] = location_id
        return location_id

    def walk(self, node, location_ids):
        parts = node.name.split(":")
        funcname = parts[1]
        func_line = int(parts[2])
        filename = parts[3]

        function_id = self.function_id(funcname, filename, func_line)

        for line, samples in node.lines.items():
            location_id = self.location_id(function_id, line)

            self._samples.append(Sample(
                location_id = [location_id] + location_ids,
                value = [samples],
            ))

        location_ids = [self.location_id(function_id, func_line)] + location_ids
        for child in node.children.values():
            self.walk(child, location_ids)

    def build(self, stats):
        tree = stats.get_tree()
        self.walk(tree, [])
        return Profile(
            sample_type = [ValueType(
                type = self.string("wall"),
                unit = self.string("milliseconds"),
            )],
            period = 1,
            string_table = self._string_table,
            function = self._functions,
            location = self._locations,
            sample = self._samples,
        )

    def build2(self, profile):
        period = 1
        for trace, trace_count, thread_id, mem_in_kb in profile.profiles:
            sample = Sample()
            sample.value.extend([trace_count * period])
            #sample.value.extend([trace_count, trace_count * period])
    
            thread_label = sample.label.add()
            thread_label.key = self.string("thread_id")
            thread_label.num = thread_id
            mem_label = sample.label.add()
            mem_label.key = self.string("total_memory")
            mem_label.num = mem_in_kb
            mem_label.num_unit = self.string("kilobytes")
    
            # Even numbered indices within `trace` are sampled stack addresses.
            # Odd indices are line numbers within the function at the previous frame.
            for idx in reversed(range(0, len(trace), 2 if profile.profile_lines else 1)):
                addr = trace[idx]
                _, function_name, start_line, filename = profile.get_addr_info(addr)
                function_name = fq_function_name(filename, function_name)
                if profile.profile_lines:  # Every other trace item is line number.
                    line_num = -trace[idx + 1]  # Line numbers are negative.
                else:  # Use function line.
                    line_num = int(start_line)
                #filename, fq_function_name = qualifier.get_name(
                #    filename, int(start_line), function_name
                #)
                function_id = self.function_id(
                    function_name, filename, int(start_line)
                )
                location_id = self.location_id(function_id, line_num)
                sample.location_id.append(location_id)

            self._samples.append(sample)

        return Profile(
            sample_type = [ValueType(
                type = self.string("wall"),
                unit = self.string("milliseconds"),
            )],
            period = 1,
            string_table = self._string_table,
            function = self._functions,
            location = self._locations,
            sample = self._samples,
        )

stats = vmprof.read_profile(sys.argv[1])
builder = ProfileBuilder()
profile = builder.build2(stats).SerializeToString()
with gzip.open(sys.argv[2], "wb") as f:
    f.write(profile)
