import argparse
import os
from bcc import BPF, USDT

class Vesta():
    PAGE_COUNT = 2048
    BPF_HEADER = """
#include <uapi/linux/ptrace.h>
#include <linux/types.h>
#include <linux/string.h>
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

int notify_%s_%s(void *ctx) {
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
    DATA_HEADER = 'probe,event_time,sample_time'    

    def generate_probe_tracing_program(self, probes):
        return '\n'.join([Vesta.BPF_HEADER] + [Vesta.BPF_PROBE_HOOK % (x, f"{self.pid}", x, x) for x in probes])

    def shutdown_hook(self, output_path, cpu, data, size):
        self.IS_RUNNING = False

    def tracing_hook(self, bpf, cpu, data, size):
        event = bpf['events'].event(data)
        self.PROBE_DATA.append('%s,%d,%d' % (
            event.probe.decode('utf-8'),
            event.ts,
            BPF.monotonic_time()
        ))
    
    def __init__(self, pid, probes, output):
        self.pid = pid
        self.probes = probes.split(',')
        self.output_directory = output
        self.IS_RUNNING = True
        self.PROBE_DATA = []        
        usdt = USDT(self.pid)
        try:
            usdt.enable_probe(probe='vm__shutdown', fn_name='notify_shutdown')
            for i in range(0, len(self.probes)):
                usdt.enable_probe(probe=self.probes[i], fn_name=f'notify_{self.probes[i]}_{self.pid}')
                code = self.generate_probe_tracing_program(self.probes)
        except Exception as e:
            print(e)
        self.bpf = BPF(text=code, usdt_contexts=[usdt])
        self.bpf['vm_shutdown'].open_perf_buffer(lambda cpu, data, size: self.shutdown_hook(
                self.output_directory,
                cpu,
                data,
                size
            ), page_cnt=Vesta.PAGE_COUNT)
        self.bpf['events'].open_perf_buffer(lambda cpu, data, size: self.tracing_hook(
            self.bpf,
            cpu,
            data,
            size
        ), page_cnt=Vesta.PAGE_COUNT)
        self.iteration = 1

    def start(self):
        self.fp = open(f"{self.output_directory}/probes_{self.iteration}.csv", 'w')
        self.fp.write(f"{Vesta.DATA_HEADER} \n")

        
    def poll(self):
        if self.IS_RUNNING:
            self.bpf.perf_buffer_poll(timeout=1)
            if len(self.PROBE_DATA) > 1000000:
                temp = self.PROBE_DATA
                self.PROBE_DATA = []
                self.fp.write('\n'.join(temp + [""]))
                
    def dump(self):
        if len(self.PROBE_DATA) > 0:
            temp = self.PROBE_DATA
            self.fp.write('\n'.join(temp + [""]))
        self.PROBE_DATA = []
        self.fp.close()
        self.iteration += 1

    def write(self):
        if len(self.PROBE_DATA) > 0:
            temp = self.PROBE_DATA
            self.PROBE_DATA = []
            self.fp.write('\n'.join(temp + [""]))

    def get_iters(self):
        return self.iteration
