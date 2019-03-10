from podcomm.exceptions import PdmError


def alert_configuration_message_body(alert_bit, activate, trigger_auto_off, duration_minutes, beep_repeat_type, beep_type,
                     alert_after_minutes=None, alert_after_reservoir=None, trigger_reservoir=False):
    if alert_after_minutes is None:
        if alert_after_reservoir is None:
            raise PdmError("Either alert_after_minutes or alert_after_reservoir must be set")
        elif not trigger_reservoir:
            raise PdmError("Trigger insulin_reservoir must be True if alert_after_reservoir is to be set")
    else:
        if alert_after_reservoir is not None:
            raise PdmError("Only one of alert_after_minutes or alert_after_reservoir must be set")
        elif trigger_reservoir:
            raise PdmError("Trigger insulin_reservoir must be False if alert_after_minutes is to be set")

    if duration_minutes > 0x1FF:
        raise PdmError("Alert duration in minutes cannot be more than %d" % 0x1ff)
    elif duration_minutes < 0:
        raise PdmError("Invalid alert duration value")

    if alert_after_minutes is not None and alert_after_minutes > 4800:
        raise PdmError("Alert cannot be set beyond 80 hours")
    if alert_after_minutes is not None and alert_after_minutes < 0:
        raise PdmError("Invalid value for alert_after_minutes")

    if alert_after_reservoir is not None and alert_after_reservoir > 50:
        raise PdmError("Alert cannot be set for more than 50 units")
    if alert_after_reservoir is not None and alert_after_reservoir < 0:
        raise PdmError("Invalid value for alert_after_reservoir")

    b0 = alert_bit << 4
    if activate:
        b0 |= 0x08
    if trigger_reservoir:
        b0 |= 0x04
    if trigger_auto_off:
        b0 |= 0x02

    b0 |= (duration_minutes >> 8) & 0x0001
    b1 = duration_minutes & 0x00ff

    if alert_after_reservoir is not None:
        reservoir_limit = int(alert_after_reservoir * 10)
        b2 = reservoir_limit >> 8
        b3 = reservoir_limit & 0x00ff
    elif alert_after_minutes is not None:
        b2 = alert_after_minutes >> 8
        b3 = alert_after_minutes & 0x00ff
    else:
        raise PdmError("Incorrect alert configuration requested")

    return bytes([b0, b1, b2, b3, beep_repeat_type, beep_type])
