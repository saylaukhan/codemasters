"""T-55: the profile generator of the simulator — numbers, statuses, idempotency.

The generator promises three things the demo data of plan.md §15 rests on: a profile hits the
status of ТЗ п. 13 it aims at, every metric stays inside the range the server accepts (T-51),
and a rerun repeats itself down to the ``measurement_uuid`` so the server answers 409 instead of
doubling the history (ADR-006).

All of it is checked without a server and without the backend: the profiles are pure functions
of the device and the moment, and ``simulate.expected_quality`` mirrors the rule of
``app.services.status`` (ADR-004), so the whole file runs on the standard library alone
(``pytest simulator/`` from the root of the repository).
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
import simulate

TZ = simulate.zone("Asia/Almaty")
THRESHOLDS = simulate.FALLBACK_THRESHOLDS
SLOTS = simulate.FALLBACK_SLOTS
DAY = date(2026, 9, 15)

# Slots of «Решения по умолчанию»: morning, the first lessons, the afternoon, the last lesson.
MORNING, LESSONS, AFTERNOON, EVENING = 0, 1, 2, 3


def device(profile: str, *, number: int = 1, wifi: bool = False) -> simulate.SimDevice:
    """One computer of a school whose contract is far above the thresholds (100/100)."""
    return simulate.SimDevice(
        device_uid=f"sim-VKO-UK-001-{number:02d}",
        hostname=f"PC-VKO-UK-001-{number:02d}",
        school_id=1,
        school_code="VKO-UK-001",
        profile=profile,
        wifi=wifi,
        contract_down_mbps=100.0,
        contract_up_mbps=100.0,
    )


def moment_of(simulated: simulate.SimDevice, slot: int, day: date = DAY) -> datetime:
    """Moment the computer measures at in that slot of that day."""
    return simulate.slot_moments(simulated.device_uid, day, SLOTS, TZ)[slot]


def item_of(simulated: simulate.SimDevice, slot: int, day: date = DAY) -> dict:
    return simulate.measurement(simulated, moment_of(simulated, slot, day), THRESHOLDS)


def test_normal_profile_keeps_thresholds_and_contract() -> None:
    """«Норма»: nothing is past a limit and the speeds reach what the contract promises."""
    simulated = device(simulate.PROFILE_NORMAL)
    for slot in range(len(SLOTS)):
        item = item_of(simulated, slot)
        assert item["connection_status"] == "online"
        assert simulate.breaches(item, THRESHOLDS) == []
        assert simulate.expected_quality(item, THRESHOLDS) == "normal"
        assert item["download_mbps"] >= simulated.contract_down_mbps
        assert item["upload_mbps"] >= simulated.contract_up_mbps


@pytest.mark.parametrize(
    ("slot", "expected"),
    [
        (MORNING, "normal"),
        (LESSONS, "unstable"),
        (AFTERNOON, "critical"),
        (EVENING, "normal"),
    ],
)
def test_peak_profile_sags_during_the_lessons(slot: int, expected: str) -> None:
    """«Деградация по часам»: the line holds in the morning and sags when the school is online."""
    simulated = device(simulate.PROFILE_PEAK)
    item = item_of(simulated, slot)
    assert simulate.expected_quality(item, THRESHOLDS) == expected


def test_peak_profile_is_worse_at_midday_than_in_the_morning() -> None:
    """The sag is in the numbers, not only in the status: latency grows over the day."""
    simulated = device(simulate.PROFILE_PEAK)
    assert item_of(simulated, AFTERNOON)["ping_ms"] > item_of(simulated, MORNING)["ping_ms"]


def test_unstable_profile_breaches_one_metric_inside_the_allowed_deviation() -> None:
    """«Нестабильно» is exactly one metric past its limit, and by less than the allowed share."""
    simulated = device(simulate.PROFILE_UNSTABLE)
    for slot in range(len(SLOTS)):
        found = simulate.breaches(item_of(simulated, slot), THRESHOLDS)
        assert len(found) == 1
        assert found[0][1] <= simulate.FALLBACK_UNSTABLE_DEVIATION_PCT
        assert simulate.expected_quality(item_of(simulated, slot), THRESHOLDS) == "unstable"


def test_critical_profile_breaches_two_metrics() -> None:
    """«Критично»: several metrics at once, which is critical at any allowed deviation."""
    simulated = device(simulate.PROFILE_CRITICAL)
    for slot in range(len(SLOTS)):
        item = item_of(simulated, slot)
        assert len(simulate.breaches(item, THRESHOLDS)) >= 2
        assert simulate.expected_quality(item, THRESHOLDS) == "critical"


def test_outage_profile_reports_no_connection() -> None:
    """«Простой»: the fact of the outage without numbers — nothing was measured (ТЗ п. 2)."""
    item = item_of(device(simulate.PROFILE_OUTAGE), LESSONS)
    assert item["connection_status"] == "offline"
    assert simulate.expected_quality(item, THRESHOLDS) == "offline"
    for metric in ("download_mbps", "upload_mbps", "ping_ms", "jitter_ms", "packet_loss_pct"):
        assert metric not in item


def test_outage_periods_are_only_for_the_outage_profile() -> None:
    """A period of ``POST /api/outages`` a day, and only from a computer that lost the line."""
    days = [DAY - timedelta(days=step) for step in range(3)]
    now = datetime.combine(DAY + timedelta(days=1), simulate.clock(23, 0), tzinfo=TZ)
    periods = simulate.device_outages(device(simulate.PROFILE_OUTAGE), days, SLOTS, TZ, now)
    assert len(periods) == len(days)
    assert all(period["started_at"] < period["ended_at"] for period in periods)
    assert simulate.device_outages(device(simulate.PROFILE_NORMAL), days, SLOTS, TZ, now) == []


def test_wifi_measurement_is_marked_and_slower() -> None:
    """A Wi-Fi measurement rates the air, not the line (ADR-012): it is marked and it is worse."""
    wired = device(simulate.PROFILE_NORMAL, number=2)
    air = replace(wired, wifi=True)
    over_the_air = item_of(air, LESSONS)
    over_the_cable = item_of(wired, LESSONS)
    assert over_the_air["iface_type"] == "wifi"
    assert over_the_cable["iface_type"] == "ethernet"
    assert over_the_air["download_mbps"] < over_the_cable["download_mbps"]
    assert over_the_air["ping_ms"] > over_the_cable["ping_ms"]


@pytest.mark.parametrize("contract", [100.0, None])
def test_wifi_keeps_the_thresholds_whatever_they_are(contract: float | None) -> None:
    """The penalty of the air is bounded by the thresholds of the server, not by a constant.

    Other thresholds and a school without a contract move the numbers, but a Wi-Fi record of a
    school of the «норма» profile stays inside the limits (ТЗ п. 11, ADR-012).
    """
    strict = simulate.Thresholds(
        download_min_mbps=50.0,
        upload_min_mbps=50.0,
        ping_max_ms=40.0,
        jitter_max_ms=10.0,
        packet_loss_max_pct=1.0,
    )
    simulated = replace(
        device(simulate.PROFILE_NORMAL, number=2, wifi=True),
        contract_down_mbps=contract,
        contract_up_mbps=contract,
    )
    for slot in range(len(SLOTS)):
        item = simulate.measurement(simulated, moment_of(simulated, slot), strict)
        assert simulate.breaches(item, strict) == []
        assert simulate.expected_quality(item, strict) == "normal"


def test_contract_profile_stays_normal_below_the_contract() -> None:
    """«Ниже договора»: the thresholds are kept, the contract is not (ТЗ п. 14, T-29)."""
    simulated = device(simulate.PROFILE_CONTRACT)
    for slot in range(len(SLOTS)):
        item = item_of(simulated, slot)
        assert simulate.expected_quality(item, THRESHOLDS) == "normal"
        assert item["download_mbps"] < simulated.contract_down_mbps
        assert item["download_mbps"] > THRESHOLDS.download_min_mbps
        assert item["upload_mbps"] < simulated.contract_up_mbps


@pytest.mark.parametrize("wifi", [False, True])
@pytest.mark.parametrize("profile", list(simulate.PROFILE_TITLES))
def test_profile_hits_the_status_it_aims_at(profile: str, wifi: bool) -> None:
    """Every profile, on every slot of a week, gets the status ``target_quality`` promises.

    Over the air as well: the server judges a Wi-Fi measurement like any other and only keeps it
    out of the status of the school (ADR-012), so a Wi-Fi computer of a school of the «норма»
    profile must not read «Критично» on its card, in its measurements and in the export.
    """
    simulated = device(profile, number=2, wifi=wifi)
    for step in range(7):
        day = DAY - timedelta(days=step)
        for moment in simulate.slot_moments(simulated.device_uid, day, SLOTS, TZ):
            item = simulate.measurement(simulated, moment, THRESHOLDS)
            assert simulate.expected_quality(item, THRESHOLDS) == simulate.target_quality(
                profile, moment
            )


@pytest.mark.parametrize("profile", list(simulate.PROFILE_TITLES))
def test_metrics_stay_inside_the_limits_of_the_server(profile: str) -> None:
    """Ranges of T-51: a value outside them is refused with 422 and the batch is lost."""
    limits = {
        "download_mbps": simulate.MAX_SPEED_MBPS,
        "upload_mbps": simulate.MAX_SPEED_MBPS,
        "ping_ms": simulate.MAX_LATENCY_MS,
        "jitter_ms": simulate.MAX_LATENCY_MS,
        "packet_loss_pct": simulate.MAX_LOSS_PCT,
        "duration_s": simulate.MAX_DURATION_S,
    }
    for number in range(1, 4):
        simulated = device(profile, number=number, wifi=number == 3)
        for slot in range(len(SLOTS)):
            item = item_of(simulated, slot)
            assert item["connection_status"] in ("online", "offline")
            assert item["agent_version"] == simulate.AGENT_VERSION
            assert datetime.fromisoformat(item["measured_at"]).tzinfo is not None
            for metric, high in limits.items():
                if metric in item:
                    assert 0.0 <= item[metric] <= high


def test_thresholds_of_the_server_drive_the_numbers() -> None:
    """Nothing is hard-coded (ТЗ п. 11): other thresholds move the numbers of the same profile."""
    strict = simulate.Thresholds(
        download_min_mbps=50.0,
        upload_min_mbps=50.0,
        ping_max_ms=40.0,
        jitter_max_ms=10.0,
        packet_loss_max_pct=1.0,
    )
    simulated = device(simulate.PROFILE_UNSTABLE)
    item = simulate.measurement(simulated, moment_of(simulated, LESSONS), strict)
    assert simulate.breaches(item, THRESHOLDS) == []
    assert len(simulate.breaches(item, strict)) == 1
    assert simulate.expected_quality(item, strict) == "unstable"


def test_measurement_repeats_itself_on_a_rerun() -> None:
    """Idempotency (ADR-006): the same computer and the same moment give the same record."""
    simulated = device(simulate.PROFILE_NORMAL)
    moment = moment_of(simulated, AFTERNOON)
    first = simulate.measurement(simulated, moment, THRESHOLDS)
    second = simulate.measurement(simulated, moment, THRESHOLDS)
    assert first == second
    assert first["measurement_uuid"] == str(simulate.measurement_uuid(simulated.device_uid, moment))


def test_measurement_uuid_differs_by_computer_and_by_moment() -> None:
    """The key separates the records: another computer or another slot is another measurement."""
    one = device(simulate.PROFILE_NORMAL, number=1)
    other = device(simulate.PROFILE_NORMAL, number=2)
    moment = moment_of(one, LESSONS)
    assert simulate.measurement_uuid(one.device_uid, moment) != simulate.measurement_uuid(
        other.device_uid, moment
    )
    assert simulate.measurement_uuid(one.device_uid, moment) != simulate.measurement_uuid(
        one.device_uid, moment + timedelta(minutes=1)
    )


def test_slot_moments_stay_inside_their_slots_and_repeat() -> None:
    """The jitter of the agent inside a slot (plan.md §4.2), but the same on every run."""
    simulated = device(simulate.PROFILE_NORMAL)
    moments = simulate.slot_moments(simulated.device_uid, DAY, SLOTS, TZ)
    assert moments == simulate.slot_moments(simulated.device_uid, DAY, SLOTS, TZ)
    assert len(moments) == len(SLOTS)
    for moment, slot in zip(moments, SLOTS, strict=True):
        assert slot.start <= moment.timetz().replace(tzinfo=None) <= slot.end
        assert moment.date() == DAY


def test_the_history_is_as_deep_as_it_was_asked_for() -> None:
    """«3 месяца истории» T-55: глубина больше ничем не обрезается (ТЗ п. 11, ADR-006).

    Сколько назад сервер примет замер — настройка ``agent_queue_retention_days``, и на время
    прогона симулятор поднимает её до нужной глубины (``queue_retention``).
    """
    now = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    assert len(simulate.history_days(5, now, TZ)) == 5
    days = simulate.history_days(90, now, TZ)
    assert len(days) == 90
    assert days == sorted(days)
    assert days[-1] == now.astimezone(TZ).date()
    assert days[0] == now.astimezone(TZ).date() - timedelta(days=89)


def test_future_moments_are_not_sent() -> None:
    """A measurement dated forward is refused as a broken clock: the run stops at ``now``."""
    simulated = device(simulate.PROFILE_NORMAL)
    now = datetime.combine(DAY, simulate.clock(12, 0), tzinfo=TZ)
    items = simulate.device_measurements(simulated, [DAY], SLOTS, TZ, THRESHOLDS, now)
    assert [datetime.fromisoformat(item["measured_at"]) <= now for item in items] == [True] * 2


def test_every_status_of_the_task_is_present_in_the_data() -> None:
    """The demo data carry all four statuses of ТЗ п. 13 and the contract mismatch of T-29."""
    schools = simulate.assign_profiles(
        [
            simulate.SimSchool(
                school_id=index + 1,
                school_code=f"VKO-SIM-{index + 1:03d}",
                full_name=f"Школа {index + 1}",
                index=index,
                contract_down_mbps=100.0,
                contract_up_mbps=100.0,
            )
            for index in range(len(simulate.PROFILE_CYCLE))
        ],
        THRESHOLDS,
    )
    profiles = {school.profile for school in schools}
    assert profiles == set(simulate.PROFILE_TITLES)
    moment = moment_of(device(simulate.PROFILE_NORMAL), LESSONS)
    statuses = {simulate.target_quality(profile, moment) for profile in profiles}
    assert {"normal", "unstable", "critical", "offline"} <= statuses


def test_the_contract_profile_goes_to_a_school_that_can_show_it() -> None:
    """A school whose contract is near the thresholds cannot be «Норма» and below the contract."""
    schools = simulate.assign_profiles(
        [
            simulate.SimSchool(
                school_id=index + 1,
                school_code=f"VKO-SIM-{index + 1:03d}",
                full_name=f"Школа {index + 1}",
                index=index,
                # The school the cycle points at has a contract of 10 Mbit/s, the next ones 100.
                contract_down_mbps=10.0 if index == 5 else 100.0,
                contract_up_mbps=10.0 if index == 5 else 100.0,
            )
            for index in range(len(simulate.PROFILE_CYCLE))
        ],
        THRESHOLDS,
    )
    below = [school for school in schools if school.profile == simulate.PROFILE_CONTRACT]
    assert len(below) == 1
    assert below[0].contract_down_mbps == 100.0
    assert schools[5].profile == simulate.PROFILE_NORMAL


def test_devices_are_spread_over_the_schools() -> None:
    """Every school gets a computer before any school gets a second one."""
    schools = [
        simulate.SimSchool(
            school_id=index + 1,
            school_code=f"VKO-SIM-{index + 1:03d}",
            full_name=f"Школа {index + 1}",
            index=index,
        )
        for index in range(3)
    ]
    devices = simulate.build_devices(schools, 7)
    assert len(devices) == 7
    assert [d.device_uid for d in devices[:3]] == [
        "sim-VKO-SIM-001-01",
        "sim-VKO-SIM-002-01",
        "sim-VKO-SIM-003-01",
    ]
    assert not devices[0].wifi
    assert {d.school_code for d in devices} == {s.school_code for s in schools}


def test_devices_carry_the_room_of_their_school() -> None:
    """The room binds a computer to the point of its school, and the export reads it (ТЗ п. 9)."""
    school = simulate.SimSchool(
        school_id=1, school_code="VKO-SIM-001", full_name="Школа 1", index=0, room="214"
    )
    devices = simulate.build_devices([school], 2)
    assert [simulated.room for simulated in devices] == ["214", "214"]
    assert simulate.room_of(school) == simulate.room_of(school)
    assert simulate.room_of(school).isdigit()


def test_batches_never_exceed_the_limit_of_the_server() -> None:
    """``POST /api/measurements/batch`` takes at most 100 items (ADR-006)."""
    parts = list(simulate.chunks(list(range(250)), simulate.MAX_BATCH_SIZE))
    assert [len(part) for part in parts] == [100, 100, 50]
    assert [number for part in parts for number in part] == list(range(250))


class FakeAdmin:
    """``AdminSession``, отвечающая из словаря: ``queue_retention`` проверяется без сервера."""

    def __init__(self, settings: dict[str, object] | None, *, patch_status: int = 200) -> None:
        self.settings = settings
        self.patch_status = patch_status
        self.patched: list[object] = []

    def request(self, method: str, path: str, *, body: object = None) -> simulate.Response:
        assert path == simulate.SETTINGS_PATH
        if method == "GET":
            if self.settings is None:
                return simulate.Response(503, {"detail": "система не настроена"})
            return simulate.Response(200, dict(self.settings))
        assert isinstance(body, dict)
        self.patched.append(body[simulate.RETENTION_SETTING])
        if self.patch_status == 200:
            self.settings = {**(self.settings or {}), **body}
        return simulate.Response(self.patch_status, self.settings)


def test_queue_retention_is_raised_for_the_run_and_put_back() -> None:
    """«3 месяца истории» T-55 заливаются через API агента и не меняют установку насовсем."""
    admin = FakeAdmin({simulate.RETENTION_SETTING: 30})

    with simulate.queue_retention(admin, 90) as depth:
        assert depth == 90
        assert admin.settings == {simulate.RETENTION_SETTING: 90}

    assert admin.settings == {simulate.RETENTION_SETTING: 30}
    assert admin.patched == [90, 30]


@pytest.mark.parametrize("error", [RuntimeError("сеть"), KeyboardInterrupt()])
def test_queue_retention_is_put_back_after_an_error_and_after_ctrl_c(
    error: BaseException,
) -> None:
    """Прерванный прогон не оставляет сервер с поднятым сроком очереди (ADR-006)."""
    admin = FakeAdmin({simulate.RETENTION_SETTING: 30})

    with pytest.raises(type(error)):
        with simulate.queue_retention(admin, 90):
            raise error

    assert admin.settings == {simulate.RETENTION_SETTING: 30}
    assert admin.patched == [90, 30]


def test_a_setting_deep_enough_is_not_touched() -> None:
    """Сервер уже принимает нужную глубину — менять настройку незачем."""
    admin = FakeAdmin({simulate.RETENTION_SETTING: 120})

    with simulate.queue_retention(admin, 90) as depth:
        assert depth == 120

    assert admin.patched == []


def test_an_old_server_without_the_setting_says_so() -> None:
    """Сборка сервера до этой настройки — внятное сообщение, а не падение на 422."""
    admin = FakeAdmin({"heartbeat_interval_s": 300})

    with pytest.raises(simulate.SimulatorError, match=simulate.RETENTION_SETTING):
        with simulate.queue_retention(admin, 90):
            pass

    assert admin.patched == []


def test_a_depth_over_the_limit_of_the_server_stops_the_run() -> None:
    """Глубже года сервер историю не примет: лучше сказать это до многочасового прогона."""
    admin = FakeAdmin({simulate.RETENTION_SETTING: 30})

    with pytest.raises(simulate.SimulatorError, match=str(simulate.MAX_RETENTION_DAYS)):
        with simulate.queue_retention(admin, simulate.MAX_RETENTION_DAYS + 1):
            pass

    assert admin.patched == []
