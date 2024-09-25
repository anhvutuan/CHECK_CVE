import re
from pathlib import Path
from typing import Any, Dict, List

PROC_CMDLINE: Path = Path("/proc/cmdline")
PROC_MODULES: Path = Path(f"/proc/modules")
PROC_SYS_KERNEL_UNPRIVILEGED_USERNS_CLONE: Path = Path(
    "/proc/sys/kernel/unprivileged_userns_clone"
)
PROC_VERSION: Path = Path("/proc/version")
BOOT_CONFIG: Path = Path(f"/boot/config-{PROC_VERSION.read_text().split(' ')[2]}")


def mkcache():
    boot_config_text: str = BOOT_CONFIG.read_text().strip()
    kconfig: Dict[str, str] = text_to_kv(boot_config_text)

    proc_sys_kernel_unprivileged_userns_clone_text = (
        {"": PROC_SYS_KERNEL_UNPRIVILEGED_USERNS_CLONE.read_text().strip()}
        if PROC_SYS_KERNEL_UNPRIVILEGED_USERNS_CLONE.exists()
        else {"": None}
    )

    proc_cmdline_text: str = PROC_CMDLINE.read_text().strip()
    cmdline: Dict[str, str] = text_to_kv(proc_cmdline_text)

    proc_modules_text: str = PROC_MODULES.read_text().strip()
    proc_modules_lines: List[str] = [l.strip() for l in proc_modules_text.splitlines()]
    proc_modules_lines = [l.split(" ") for l in proc_modules_lines]
    modules: Dict[str, str] = {x[0]: x[4] for x in proc_modules_lines}

    return {
        BOOT_CONFIG: kconfig,
        PROC_SYS_KERNEL_UNPRIVILEGED_USERNS_CLONE: proc_sys_kernel_unprivileged_userns_clone_text,
        PROC_CMDLINE: cmdline,
        PROC_MODULES: modules,
    }


def text_to_kv(text: str) -> Dict[str, str]:
    kv_pattern: re.Pattern = re.compile(r"\s*?(.*?)\s*=\s*(.*)")
    items = text.splitlines()
    items = [i.strip() for i in items if i != ""]
    items = [i for i in items if not i.startswith("#")]
    items = [kv_pattern.findall(i) for i in items]
    items = [i[0] for i in items]
    items = [i for i in items if len(i) >= 2]
    return {x[0]: x[1] for x in items}


# https://nvd.nist.gov/vuln/detail/CVE-2024-1086
def check_version(version: str) -> bool:
    return any(
        [
            "3.15" <= version < "6.1.76",
            "6.2" <= version < "6.6.15",
            "6.7" <= version < "6.7.3",
            "6.8.0" <= version <= "6.8.0",
        ]
    )


def main():
    proc_version_text: str = PROC_VERSION.read_text().strip()
    full_version: str = proc_version_text.split(" ")[2]
    short_version = full_version.split("-")[0]
    cache: Dict[str, Any] = mkcache()
    expected_values: Dict[str, Any] = {
        BOOT_CONFIG: {
            "CONFIG_INIT_ON_FREE_DEFAULT_ON": [None, "is not set"],
            "CONFIG_NF_TABLES": ["m", "y"],
            "CONFIG_USER_NS": ["y"],
        },
        PROC_CMDLINE: {"init_on_free": [None, "0"]},
        PROC_MODULES: {"nf_tables": ["Live"]},
        PROC_SYS_KERNEL_UNPRIVILEGED_USERNS_CLONE: {"": [None, "1"]},
    }
    if "6.4.0" <= short_version:
        expected_values[BOOT_CONFIG]["CONFIG_INIT_ON_ALLOC_DEFAULT_ON"] = [
            None,
            "is not set",
        ]
        expected_values[PROC_CMDLINE]["init_on_alloc"] = [None, "0"]

    saved_by = []
    all_values = []
    result = [
        "CVE-2024-1086 Privesc Check",
        f"kernel version: {full_version}",
    ]

    if check_version(short_version):
        result.append(f"[+] version {short_version} is vulnerable")
        for fpath, keys in expected_values.items():
            data = cache.get(fpath)
            for key, allowed_v in keys.items():
                actual = data.get(key)
                all_values.append(f"{fpath} > {key}: {actual}")
                if actual not in allowed_v:
                    saved_by.append(
                        f"[+] saved by {fpath} > {key} expected {allowed_v}, got {actual}"
                    )

        result = [*result, *all_values, *saved_by]
        if saved_by:
            result = [*result, "[+] kernel config is not vulnerable"]
        else:
            result.append("[+] WARNING! KERNEL CONFIG IS VULNERABLE")
    else:
        result.append(f"[+] version {short_version} is not vulnerable")

    result = ["=" * 64, *result, "=" * 64]
    print("\n".join(result))


if __name__ == "__main__":
    main()
