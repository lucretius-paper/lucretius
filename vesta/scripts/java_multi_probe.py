import argparse
import os
from bcc import BPF, USDT
PAGE_COUNT = 2048
BPF_HEADER = """
#include <uapi/linux/ptrace.h>
#include <linux/types.h>
BPF_ARRAY(counts, u64, 400);

struct data_t {
    u32 pid;
    u64 ts;
    char probe[100];
    char comm[100];
};

BPF_PERF_OUTPUT(vm_shutdown);
BPF_PERF_OUTPUT(events);

int notify_shutdown(void *ctx) {
     struct data_t data = {};
     data.pid = bpf_get_current_pid_tgid();
     data.ts = bpf_ktime_get_ns();
     bpf_get_current_comm(&data.comm, sizeof(data.comm));
     vm_shutdown.perf_submit(ctx, &data, sizeof(data));
     return 0;
}
"""

BPF_PROBE_HOOK = """

int notify_%s(void *ctx) {
    struct data_t data = {};
    data.pid = bpf_get_current_pid_tgid();
    data.ts = bpf_ktime_get_ns();
    strcpy(data.probe, "%s");
    bpf_get_current_comm(&data.comm, sizeof(data.comm));
    events.perf_submit(ctx, &data, sizeof(data));
    //bpf_trace_printk("hit probe %s\\n");
    return 0;
}
"""

IS_RUNNING = True
PROBE_DATA = []
DATA_HEADER = 'probe,event_time,sample_time'


def generate_probe_tracing_program(probes):
    return '\n'.join([BPF_HEADER] + [BPF_PROBE_HOOK % (x, x, x) for x in probes])


def shutdown_hook(output_path, cpu, data, size):
    global IS_RUNNING
    IS_RUNNING = False

    # with open(os.path.join(output_path, 'probes.csv'), 'a') as fp_hook:
    #     fp_hook.write('\n'.join([""] + PROBE_DATA) + '\n')
        # fp.write('\n'.join([DATA_HEADER] + PROBE_DATA) + '\n')



def tracing_hook(bpf, cpu, data, size):
    event = bpf['events'].event(data)
    PROBE_DATA.append('%s,%d,%d' % (
        event.probe.decode('utf-8'),
        event.ts,
        BPF.monotonic_time()
    ))


def add_tracing_hook(bpf, probe):
    bpf[probe].open_perf_buffer(
        lambda cpu, data, size: tracing_hook(
            bpf,
            probe,
            cpu,
            data,
            size
        ), page_cnt=PAGE_COUNT
    )


def parse_args():
    parser = argparse.ArgumentParser(description='jvm probe tracer')
    parser.add_argument('-p', '--pid', type=int, help='java process to trace')
    parser.add_argument(
        '--probes',
        default='monitor__wait',
        type=str,
        help='jvm probes to trace'
    )
    parser.add_argument(
        '--output_directory',
        default='.',
        type=str,
        help='location to write the log'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    probes = args.probes.split(',')

    usdt = USDT(pid=args.pid)
    usdt.enable_probe(probe='vm__shutdown', fn_name='notify_shutdown')
    system_probes = []
    for i in range(0, len(probes)):
        if ":" in probes[i]:
            system_probes.append(probes[i])
            probes[i] = probes[i].split(":")[1]
        else:
            usdt.enable_probe(probe=probes[i], fn_name='notify_%s' % probes[i])

    code = generate_probe_tracing_program(probes)
    # print(code)
    bpf = BPF(text=code, usdt_contexts=[usdt])
    # bpf = BPF(text=code)
    for sys_probe in system_probes:
        bpf.attach_tracepoint(
            tp=sys_probe, fn_name=f"notify_{sys_probe.split(':')[1]}")
    bpf['vm_shutdown'].open_perf_buffer(lambda cpu, data, size: shutdown_hook(
        args.output_directory,
        cpu,
        data,
        size
    ), page_cnt=PAGE_COUNT)
    bpf['events'].open_perf_buffer(lambda cpu, data, size: tracing_hook(
        bpf,
        cpu,
        data,
        size
    ), page_cnt=PAGE_COUNT)
    # the commented sections were added to help with piecemeal writing (not necessary)
    fp = open(os.path.join(args.output_directory, 'probes.csv'), 'w')
    fp.write(f"{DATA_HEADER} \n")
    global PROBE_DATA
    while IS_RUNNING:
        bpf.perf_buffer_poll(timeout=1)
        if len(PROBE_DATA) > 1000000:
            temp = PROBE_DATA
            PROBE_DATA = []
            fp.write('\n'.join([""] + temp) + '\n')
    if len(PROBE_DATA) > 0:
        temp = PROBE_DATA
        PROBE_DATA = []
        fp.write('\n'.join([""] + temp) + '\n')
    fp.close()


if __name__ == '__main__':
    main()
