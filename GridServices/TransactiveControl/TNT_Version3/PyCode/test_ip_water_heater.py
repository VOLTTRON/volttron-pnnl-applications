"""
test_ip_water_heater.py
This contains a suite of tests for methods in ip_water_heater.py concerning class IpWaterHeater. From the command line,
enter                                       'run test_ip_water_heater.py'

    January 2020
    Donald J Hammerstrom, Ph.D.
    Battelle, Pacific Northwest Division
    Project 73346 for Islay Power
    ** Contents are Business Sensitive **
    Copyright 2020
"""

# Import statements ****************************************************************************************************
from ip_water_heater import IpWaterHeater
from ip_constants import Constant


# from ip_occupancy_modes import OccupancyMode
# from ip_occupancy_settings import OccupancySetting
# from ip_weekdays import Weekday


def test_calculate_comfort_cost():
    print('Running test_calculate_comfort_cost().')

    # CASE 1 ***********************************************************************************************************
    print('  Case 1: Single water temperature equal to the preferred temperature. The reported cost should be zero.')

    test_asset = IpWaterHeater()

    temperatures = [test_asset.preferredDeliveryTemperature]

    assert len(temperatures) == 1, 'Only a single temperature should be submitted for this test.'
    assert temperatures[0] == test_asset.preferredDeliveryTemperature, \
        'The temperature should be the preferred temperature'

    cost = None
    try:
        cost = test_asset.calculate_comfort_cost(temperatures[:])
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS:', warning)

    assert isinstance(cost, float), 'Only one floating cost value should be reported by this method.'
    assert cost == 0, 'The cost at the preferred temperature is 0.'

    # CASE 2 ***********************************************************************************************************
    print('  Case 2: Single water temperature equal to the maximum temperature. The cost should be property "factor". ')

    test_asset = IpWaterHeater()
    temperatures = [test_asset.maximumComfortableTemperature]

    assert len(temperatures) == 1, 'Only a single temperature should be submitted for this test.'
    assert temperatures[0] == test_asset.maximumComfortableTemperature, \
        'The temperature should be the maximum comfortable temperature'

    cost = None
    try:
        cost = test_asset.calculate_comfort_cost(temperatures[:])
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS:', warning)

    assert isinstance(cost, float), 'Only one floating cost value should be reported by this method.'
    assert cost == test_asset.factor, 'The cost at the preferred temperature should be equal to property "factor".'

    # CASE 3 ***********************************************************************************************************
    print('  Case 3: Single water temperature equal to minimum temperature. The cost should be property "factor".')

    test_asset = IpWaterHeater()
    temperatures = [test_asset.minimumComfortableTemperature]

    assert len(temperatures) == 1, 'Only a single temperature should be submitted for this test.'
    assert temperatures[0] == test_asset.minimumComfortableTemperature, \
        'The temperature should be the minimum comfortable temperature'

    cost = None
    try:
        cost = test_asset.calculate_comfort_cost(temperatures[:])
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS:', warning)

    assert isinstance(cost, float), 'Only one floating cost value should be reported by this method.'
    assert cost == test_asset.factor, 'The cost at the preferred temperature should be equal to property "factor".'

    # CASE 4 ***********************************************************************************************************
    print('  Case 4: Single temperature halfway between preferred and maximum temperatures.')

    test_asset = IpWaterHeater()
    temperature = (test_asset.maximumComfortableTemperature + test_asset.preferredDeliveryTemperature) / 2
    temperatures = [temperature]
    test_asset.gamma = 1  # So the cost result may be estimated as 1/2 property factor.

    assert len(temperatures) == 1, 'Only a single temperature should be submitted for this test.'
    assert temperatures[0] == temperature, \
        'The temperature should be halfway between preferred and maximum temperatures.'

    cost = None
    try:
        cost = test_asset.calculate_comfort_cost(temperatures[:])
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS:', warning)

    assert isinstance(cost, float), 'Only one floating cost value should be reported by this method.'
    assert cost == test_asset.factor / 2, \
        'The cost at the preferred temperature should be equal to half of property "factor".'

    # CASE 5 ***********************************************************************************************************
    print('  Case 5: Single temperature that exceeds the hard maximum temperature limit.')

    test_asset = IpWaterHeater()
    temperature = Constant.MAXIMUM_ALLOWED_TEMPERATURE + 1
    temperatures = [temperature]

    assert len(temperatures) == 1, 'Only a single temperature should be submitted for this test.'
    assert temperatures[0] == temperature, \
        'The temperature should be greater than the maximum allowed temperature.'

    cost = None
    try:
        cost = test_asset.calculate_comfort_cost(temperatures[:])
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS:', warning)

    assert isinstance(cost, float), 'Only one floating cost value should be reported by this method.'
    assert cost > test_asset.factor, \
        'The cost must be much greater than property "factor" if the temperature was greater than the maximum.'

    # CASE 6 ***********************************************************************************************************
    print('  Case 6: Multiple temperatures.')

    test_asset = IpWaterHeater()
    temperatures = [test_asset.minimumComfortableTemperature, test_asset.preferredDeliveryTemperature,
                    test_asset.maximumComfortableTemperature]

    assert len(temperatures) == 3, 'Only a single temperature should be submitted for this test.'

    cost = None
    try:
        cost = test_asset.calculate_comfort_cost(temperatures[:])
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS:', warning)

    assert isinstance(cost, float), 'Only one floating cost value should be reported by this method.'
    assert cost == test_asset.factor * 2 / 3, \
        'The cost must be the average of preferred (0), and two extremum (property factor).'

    print('test_calculate_comfort_cost() ran to completion.\n')


def test_get_cost_mode():
    print('Running test_set_cost_mode().')
    test_asset = IpWaterHeater()
    cost_mode = 0.5
    test_asset.costModeSetting = cost_mode

    print('  Normal case.')

    try:
        returned_cost_mode = test_asset.get_cost_mode()
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)
        returned_cost_mode = None

    assert test_asset.costModeSetting == cost_mode, "The asset's cost mode was unexpectedly changed."
    assert returned_cost_mode == cost_mode, 'An unexpected value was returned.'

    print('test_get_cost_mode() ran to completion.\n')


def test_get_current_lower_temperature():
    print('Running test_get_current_lower_temperature().')
    print('  Case 1: The current lower temperature can be directly measured.')
    print('  Case 2: The current lower temperature must be inferred from model predictive control.')
    print('  Case 3: The current lower temperature is unavailable by measurement or from model predictive control')
    print('test_get_current_lower_temperature() ran to completion.\n')


def test_get_current_upper_temperature():
    print('Running test_get_current_upper_temperature().')
    print('  Case 1: The current upper temperature can be directly measured.')
    print('  Case 2: The current upper temperature must be inferred from model predictive control.')
    print('  Case 3: The current upper temperature is unavailable by measurement or from model predictive control')
    print('test_get_current_upper_temperature() ran to completion.\n')


def test_get_inflow_temperature():
    print('Running test_get_inflow_temperature().')
    print('  Case 1: The current inlet temperature can be directly measured.')
    print('  Case 2: The current inlet temperature is unavailable, so the initialized value is used instead.')
    print('test_get_inflow_temperature() ran to completion.\n')


def test_get_maximum_comfortable_temperature():
    print('test_get_maximum_comfortable_temperature().')

    print('  Case 1: Normal case. Maximum temperature is retrieved accurately within default temperature set.')
    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    old_maximum_comfortable_temperature = test_asset.maximumComfortableTemperature
    maximum_thermostat_set_point = max(test_asset.lowerTemperatureSetPoint, test_asset.upperTemperatureSetPoint)

    assert test_asset.maximumComfortableTemperature > test_asset.preferredDeliveryTemperature, \
        'The preferred temperature must lie below maximum comfortable temperatures'
    assert test_asset.maximumComfortableTemperature <= maximum_thermostat_set_point, \
        'The water heater cannot heat the water above the highest of the lower and upper thermostat set points.'

    try:
        test_asset.get_maximum_comfortable_temperature()
        print('  - The test ran without errors.')

    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.maximumComfortableTemperature == old_maximum_comfortable_temperature, \
        'The wrong temperature was stored.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('test_get_maximum_comfortable_temperature() ran to completion.\n')


def test_get_minimum_comfortable_temperature():
    print('test_get_minimum_comfortable_temperature().')

    print('  Case 1: Normal case. Minimum temperature is retrieved accurately within default temperature set.')
    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    old_minimum_comfortable_temperature = test_asset.minimumComfortableTemperature

    assert test_asset.minimumComfortableTemperature < test_asset.preferredDeliveryTemperature \
           < test_asset.maximumComfortableTemperature, \
        'The preferred temperature must lie between the minimum and maximum comfortable temperatures'

    try:
        test_asset.get_minimum_comfortable_temperature()
        print('  - The test ran without errors.')

    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.minimumComfortableTemperature == old_minimum_comfortable_temperature, \
        'The wrong temperature was stored.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('test_get_minimum_comfortable_temperature() ran to completion.\n')


def test_get_preferred_delivery_temperature():
    print('Running test_get_preferred_delivery_temperature().')

    print('  Case 1: Normal case. Preferred temperature retrieved accurately within default temperature set.')
    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature

    assert test_asset.minimumComfortableTemperature < test_asset.preferredDeliveryTemperature \
           < test_asset.maximumComfortableTemperature, \
        'The preferred temperature must lie between the minimum and maximum comfortable temperatures'

    try:
        test_asset.get_preferred_delivery_temperature()
        print('  - The test ran without errors.')

    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, 'The wrong temperature was stored.'

    print('test_get_preferred_delivery_temperature ran to completion.\n')


def test_get_risk_mode():
    print('Running test_set_risk_mode().')
    test_asset = IpWaterHeater()
    risk_mode = 0.5
    test_asset.riskModeSetting = risk_mode

    print('  Case 1: Risk mode exists and is read.')

    try:
        returned_risk_mode = test_asset.get_risk_mode()
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)
        returned_risk_mode = None

    assert test_asset.riskModeSetting == risk_mode, "The asset's risk mode was unexpectedly changed."
    assert returned_risk_mode == risk_mode, 'An unexpected value was returned.'

    print('test_get_risk_mode() ran to completion.\n')


def test_model_water_use():
    print('Running test_model_water_use().')
    print('  Case 1: ')
    print('test_model_water_use() ran to completion.\n')


def test_predict_temperatures():
    print('Running test_predict_temperatures().')
    print('  Case 1: ')
    print('test_predict_temperatures() ran to completion.\n')


def test_schedule_power():
    print('Running test_schedule_power().')
    print('test_schedule_power() ran to completion.\n')


def test_set_cost_mode():
    print('Running test_set_cost_mode().')
    test_asset = IpWaterHeater()

    print('  Case 1: Normal case. Provided parameter lies in (0, 1).')
    cost_mode = 0.5

    try:
        new_cost_mode = test_asset.set_cost_mode(cost_mode)
        print('  The method ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)
        new_cost_mode = None

    assert test_asset.costModeSetting == cost_mode, "The asset's cost mode was not as expected."
    assert new_cost_mode == cost_mode, 'An unexpected value was returned.'

    print('  Case 2: Provided parameter > 1.')
    cost_mode = 2

    try:
        new_cost_mode = test_asset.set_cost_mode(cost_mode)
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS', warning)

    assert test_asset.costModeSetting == 1, "The asset's cost mode was not as expected."
    assert new_cost_mode == 1, 'An unexpected value was returned.'

    print('  Case 3: Provided parameter < 0.')
    cost_mode = -2

    try:
        new_cost_mode = test_asset.set_cost_mode(cost_mode)
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.costModeSetting == 0, "The asset's cost mode was not as expected."
    assert new_cost_mode == 0, 'An unexpected value was returned.'

    print('test_set_cost_mode() ran to completion.\n')


def test_set_maximum_comfortable_temperature():
    print('Running test_set_maximum_comfortable_temperature().')

    print('  Case 1: Set maximum comfortable temperature within default range')  # *************************************
    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    old_maximum_temperature = test_asset.maximumComfortableTemperature

    assert test_asset.maximumComfortableTemperature > test_asset.preferredDeliveryTemperature, \
        'The preferred temperature must lie below the maximum comfortable temperatures'

    try:
        test_asset.set_maximum_comfortable_temperature(old_maximum_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS', warning)

    assert test_asset.maximumComfortableTemperature == old_maximum_temperature, \
        'the maximum temperature should not have changed.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('  Case 2: Try to set maximum temperature below the preferred. Maximum is set 1 degree above preferred.')  # *

    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    new_maximum_temperature = old_preferred_temperature - 1

    assert new_maximum_temperature <= old_preferred_temperature + 1, \
        'In this case, the new maximum temperature must be less than the old preferred temperature by at least 1 C.'

    try:
        test_asset.set_maximum_comfortable_temperature(new_maximum_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.maximumComfortableTemperature > new_maximum_temperature, \
        'The maximum temperature should be greater than requested.'
    assert test_asset.maximumComfortableTemperature >= test_asset.preferredDeliveryTemperature + 1, \
        'The maximum temperature should have been increase to lie at least 1 degree above the preferred temperature.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('  Case 3: Try to set maximum temperature above the hard limit. Maximum is raised to the hard limit.')  # ****

    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    maximum_limit = Constant.MAXIMUM_ALLOWED_TEMPERATURE
    new_maximum_temperature = maximum_limit + 1

    # In this case the thermostat set points must be elevated greatly above the maximum comfortable temperature
    test_asset.upperTemperatureSetPoint = new_maximum_temperature + 100
    test_asset.lowerTemperatureSetPoint = new_maximum_temperature + 100

    assert new_maximum_temperature > maximum_limit, \
        'In this case, the new maximum temperature must lie above the hard minimum limit.'

    try:
        test_asset.set_maximum_comfortable_temperature(new_maximum_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.maximumComfortableTemperature < new_maximum_temperature, \
        'The maximum temperature should be less than requested.'
    assert test_asset.maximumComfortableTemperature == maximum_limit, \
        'The minimum temperature should have been set equal to the maximum limit.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('  Case 4: Try to set maximum temperature above the highest thermostat set point. Maximum is reduced.')  # ***

    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature

    maximum_temperature_set_point = max(test_asset.upperTemperatureSetPoint, test_asset.lowerTemperatureSetPoint)
    new_maximum_temperature = maximum_temperature_set_point + 1

    assert new_maximum_temperature > test_asset.upperTemperatureSetPoint, \
        'In this case, the new maximum temperature must lie above the upper thermostat set point.'
    assert new_maximum_temperature > test_asset.lowerTemperatureSetPoint, \
        'In this case, the new maximum temperature must lie above the lower thermostat set point.'

    try:
        test_asset.set_maximum_comfortable_temperature(new_maximum_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.maximumComfortableTemperature < new_maximum_temperature, \
        'The maximum temperature should be less than requested.'
    assert test_asset.maximumComfortableTemperature == maximum_temperature_set_point, \
        'The temperature should have been set equal to the greater of the upper and lower thermostat set points.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('test_set_maximum_comfortable_temperature() ran to completion.\n')


def test_set_minimum_comfortable_temperature():
    print('Running test_set_minimum_comfortable_temperature().')

    print('  Case 1: Set minimum comfortable temperature within default range')  # *************************************
    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    old_minimum_temperature = test_asset.minimumComfortableTemperature

    assert test_asset.minimumComfortableTemperature < test_asset.preferredDeliveryTemperature \
           < test_asset.maximumComfortableTemperature, \
        'The preferred temperature must lie between the minimum and maximum comfortable temperatures'

    try:
        test_asset.set_minimum_comfortable_temperature(old_minimum_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print('  - THE TEST ENCOUNTERED ERRORS', warning)

    assert test_asset.minimumComfortableTemperature == old_minimum_temperature, \
        'the minimum temperature should not have changed.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('  Case 2: Try to set minimum temperature above the preferred. Minimum is set 1 degree below preferred.')  # *

    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    new_minimum_temperature = old_preferred_temperature + 1

    assert new_minimum_temperature >= old_preferred_temperature - 1, \
        'In this case, the new minimum temperature must exceed the old preferred temperature by at least 1 deg. C.'

    try:
        test_asset.set_minimum_comfortable_temperature(new_minimum_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.minimumComfortableTemperature < new_minimum_temperature, \
        'The minimum temperature should be less than requested.'
    assert test_asset.minimumComfortableTemperature <= test_asset.preferredDeliveryTemperature - 1, \
        'The minimum temperature should have been reduced to lie at least 1 degree below the preferred temperature.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('  Case 3: Try to set minimum temperature below the hard limit. Minimum is raised to the hard limit.')  # ****

    test_asset = IpWaterHeater()
    old_preferred_temperature = test_asset.preferredDeliveryTemperature
    minimum_limit = Constant.MINIMUM_ALLOWED_TEMPERATURE
    new_minimum_temperature = minimum_limit - 1

    assert new_minimum_temperature < minimum_limit, \
        'In this case, the new minimum temperature must lie below the hard minimum limit.'

    try:
        test_asset.set_minimum_comfortable_temperature(new_minimum_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.minimumComfortableTemperature > new_minimum_temperature, \
        'The minimum temperature should be greater than requested.'
    assert test_asset.minimumComfortableTemperature == minimum_limit, \
        'The minimum temperature should have been set equal to the minimum limit.'
    assert test_asset.preferredDeliveryTemperature == old_preferred_temperature, \
        'The preferred temperature should not have changed.'

    print('test_set_minimum_comfortable_temperature() ran to completion.\n')


def test_set_preferred_delivery_temperature():
    print('Running test_set_preferred_delivery_temperature().')

    print('  Case 1: Set preferred temperature within default range')  # ***********************************************
    test_asset = IpWaterHeater()
    new_preferred_temperature = test_asset.preferredDeliveryTemperature

    assert test_asset.minimumComfortableTemperature < test_asset.preferredDeliveryTemperature \
           < test_asset.maximumComfortableTemperature, \
        'The preferred temperature must lie between the minimum and maximum comfortable temperatures'

    try:
        test_asset.set_preferred_delivery_temperature(new_preferred_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.preferredDeliveryTemperature == new_preferred_temperature, \
        'Preferred temperature should not have changed.'

    print('  Case 2: Try to set preferred temperature above the maximum. Preferred is set 1 degree below maximum.')  # *

    test_asset = IpWaterHeater()
    old_maximum_comfortable_temperature = test_asset.maximumComfortableTemperature
    new_preferred_temperature = old_maximum_comfortable_temperature + 1

    assert new_preferred_temperature >= old_maximum_comfortable_temperature - 1, \
        'In this case, the new preferred temperature must exceed the old maximum comfortable temperature.'

    try:
        test_asset.set_preferred_delivery_temperature(new_preferred_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)
        pass

    assert test_asset.preferredDeliveryTemperature < new_preferred_temperature, \
        'The preferred temperature should be less than requested.'
    assert test_asset.maximumComfortableTemperature >= test_asset.preferredDeliveryTemperature + 1, \
        'The preferred temperature should have been reduced to lie at least 1 degree below the maximum temperature.'
    assert test_asset.maximumComfortableTemperature == old_maximum_comfortable_temperature, \
        'The maximum comfortable temperature should not have changed.'

    print('  Case 3: Set preferred temp. below minimum. Minimum comfortable temperature is reduced.')

    test_asset = IpWaterHeater()
    old_minimum_comfortable_temperature = test_asset.minimumComfortableTemperature
    new_preferred_temperature = old_minimum_comfortable_temperature - 1

    assert new_preferred_temperature <= old_minimum_comfortable_temperature + 1, \
        'In this case, the new preferred temperature must lie below the old minimum comfortable temperature.'

    try:
        test_asset.set_preferred_delivery_temperature(new_preferred_temperature)
        print('  - The test ran without errors.')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)
        pass

    assert test_asset.preferredDeliveryTemperature > new_preferred_temperature, \
        'The preferred temperature should be greater than that requested.'
    assert test_asset.minimumComfortableTemperature <= test_asset.preferredDeliveryTemperature - 1, \
        'The preferred temperature should have been increase to lie at least 1 degree above the minimum temperature.'
    assert test_asset.minimumComfortableTemperature == old_minimum_comfortable_temperature, \
        'The maximum comfortable temperature should not have changed.'

    print('test_set_preferred_delivery_temperature() ran to completion.\n')


def test_set_risk_mode():
    print('Running test_set_risk_mode().')
    test_asset = IpWaterHeater()

    print('  Case 1: Normal case. Provided parameter lies in (0, 1).')
    risk_mode = 0.5

    try:
        new_risk_mode = test_asset.set_risk_mode(risk_mode)
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)
        new_risk_mode = None

    assert test_asset.riskModeSetting == risk_mode, "The asset's risk mode was not as expected."
    assert new_risk_mode == risk_mode, 'An unexpected value was returned.'

    print('  Case 2: Provided parameter > 1.')
    risk_mode = 2

    try:
        new_risk_mode = test_asset.set_risk_mode(risk_mode)
        print('  The test ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.riskModeSetting == 1, "The asset's cost mode was not as expected."
    assert new_risk_mode == 1, 'An unexpected value was returned.'

    print('  Case 3: Provided parameter < 0.')
    risk_mode = -2

    try:
        new_risk_mode = test_asset.set_risk_mode(risk_mode)
        print('  - The test ran without errors')
    except RuntimeWarning as warning:
        print(' - THE TEST ENCOUNTERED ERRORS:', warning)

    assert test_asset.riskModeSetting == 0, "The asset's cost mode was not as expected."
    assert new_risk_mode == 0, 'An unexpected value was returned.'

    print('test_set_risk_mode() ran to completion.\n')


def test_update_vertices():
    print('Running test_update_vertices().')
    print('  Case 1:')
    print('test_update_vertices() ran to completion.\n')


if __name__ == '__main__':
    test_calculate_comfort_cost()  # Done
    test_get_cost_mode()  # Done
    test_get_current_lower_temperature()
    test_get_current_upper_temperature()
    test_get_inflow_temperature()
    test_get_maximum_comfortable_temperature()  # Done
    test_get_minimum_comfortable_temperature()  # Done
    test_get_preferred_delivery_temperature()  # Done
    test_get_risk_mode()  # Done
    test_model_water_use()
    test_predict_temperatures()
    test_schedule_power()
    test_set_cost_mode()  # Done
    test_set_maximum_comfortable_temperature()  # Done
    test_set_minimum_comfortable_temperature()  # Done
    test_set_preferred_delivery_temperature()  # Done
    test_set_risk_mode()  # Done
    test_update_vertices()
