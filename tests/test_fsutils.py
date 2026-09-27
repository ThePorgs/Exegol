from exegol.utils.FsUtils import REQUIRED_OVPN_DNS_LINES, missing_ovpn_dns_lines


def test_missing_ovpn_dns_lines_all_missing():
    assert missing_ovpn_dns_lines([]) == list(REQUIRED_OVPN_DNS_LINES)


def test_missing_ovpn_dns_lines_all_present():
    lines = [
        "remote vpn.example.com 1194\n",
        "  down /etc/openvpn/update-resolv-conf  \n",
        "cipher AES-256-CBC\n",
        "script-security 2\n",
        "up /etc/openvpn/update-resolv-conf\n",
    ]
    assert missing_ovpn_dns_lines(lines) == []


def test_missing_ovpn_dns_lines_partial():
    lines = ["remote vpn.example.com 1194\n", "script-security 2\n"]
    assert missing_ovpn_dns_lines(lines) == [
        "up /etc/openvpn/update-resolv-conf",
        "down /etc/openvpn/update-resolv-conf",
    ]
