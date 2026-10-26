#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <unistd.h>
#include <dlfcn.h>
#include <execinfo.h>
#include <sys/syscall.h>

static void log_msg(const char *msg, int sig, int code, int pid, int uid) {
    FILE *f = fopen("/tmp/nosigterm.log", "a");
    if (f) {
        fprintf(f, "[nosigterm] pid=%d tid=%ld %s sig=%d code=%d si_pid=%d si_uid=%d\n",
                getpid(), syscall(SYS_gettid), msg, sig, code, pid, uid);
        void *bt[16];
        int n = backtrace(bt, 16);
        char **syms = backtrace_symbols(bt, n);
        if (syms) {
            for (int i = 0; i < n; i++) {
                fprintf(f, "  bt[%d]: %s\n", i, syms[i]);
            }
            free(syms);
        }
        fclose(f);
    }
}

static void ignore_sigterm_handler(int sig, siginfo_t *info, void *ucontext) {
    int code = info ? info->si_code : -999;
    int spid = info ? info->si_pid : -999;
    int suid = info ? (int)info->si_uid : -999;
    log_msg("CAUGHT_AND_IGNORED_SIGNAL", sig, code, spid, suid);
}

typedef int (*sigaction_fn)(int, const struct sigaction *, struct sigaction *);

__attribute__((constructor))
static void init_nosigterm(void) {
    sigaction_fn real_sigaction = (sigaction_fn)dlsym(RTLD_NEXT, "sigaction");
    if (real_sigaction) {
        struct sigaction newact = {0};
        newact.sa_sigaction = ignore_sigterm_handler;
        newact.sa_flags = SA_SIGINFO | SA_RESTART;
        real_sigaction(SIGTERM, &newact, NULL);
        real_sigaction(SIGHUP, &newact, NULL);
    }
    log_msg("INIT_NOSIGTERM", 0, 0, getpid(), getuid());
}

int sigaction(int signum, const struct sigaction *act, struct sigaction *oldact) {
    static sigaction_fn real_sigaction = NULL;
    if (!real_sigaction) real_sigaction = (sigaction_fn)dlsym(RTLD_NEXT, "sigaction");
    if (signum == SIGTERM || signum == SIGHUP || signum == SIGINT) {
        struct sigaction newact;
        if (act) {
            newact = *act;
            newact.sa_sigaction = ignore_sigterm_handler;
            newact.sa_flags |= SA_SIGINFO | SA_RESTART;
            log_msg("INTERCEPTED_sigaction", signum, 0, 0, 0);
            return real_sigaction(signum, &newact, oldact);
        }
    }
    return real_sigaction(signum, act, oldact);
}

typedef sighandler_t (*signal_fn)(int, sighandler_t);
sighandler_t signal(int signum, sighandler_t handler) {
    static signal_fn real_signal = NULL;
    if (!real_signal) real_signal = (signal_fn)dlsym(RTLD_NEXT, "signal");
    if (signum == SIGTERM || signum == SIGHUP || signum == SIGINT) {
        struct sigaction newact = {0};
        newact.sa_sigaction = ignore_sigterm_handler;
        newact.sa_flags = SA_SIGINFO | SA_RESTART;
        sigaction_fn real_sigaction = (sigaction_fn)dlsym(RTLD_NEXT, "sigaction");
        real_sigaction(signum, &newact, NULL);
        log_msg("INTERCEPTED_signal", signum, 0, 0, 0);
        return SIG_DFL;
    }
    return real_signal(signum, handler);
}

typedef int (*kill_fn)(pid_t, int);
int kill(pid_t pid, int sig) {
    static kill_fn real_kill = NULL;
    if (!real_kill) real_kill = (kill_fn)dlsym(RTLD_NEXT, "kill");
    if (pid == getpid() && (sig == SIGTERM || sig == SIGUSR1 || sig == SIGINT)) {
        log_msg("BLOCKED_self_kill", sig, 0, pid, getuid());
        return 0;
    }
    return real_kill(pid, sig);
}
