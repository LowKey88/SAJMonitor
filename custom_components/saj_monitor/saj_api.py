"""SAJ API client for the SAJ Solar & Battery Monitor integration."""
import logging
import asyncio
import async_timeout
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import aiohttp
import hashlib
import hmac
import base64
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    TOKEN_URL,
    DEVICE_INFO_URL,
    PLANT_STATS_URL,
    HISTORY_DATA_URL,
    LOAD_MONITORING_URL,
    REALTIME_DATA_URL,
    DEVICE_TYPE_SOLAR,
    DEVICE_TYPE_BATTERY,
)

_LOGGER = logging.getLogger(__name__)

class SajApiClient:
    """API client for SAJ Solar & Battery Monitor."""

    def __init__(self, app_id: str, app_secret: str, session: aiohttp.ClientSession):
        """Initialize the API client."""
        self._app_id = app_id
        self._app_secret = app_secret
        self._session = session
        self._token = None
        self._token_expires_at = dt_util.now()
        
    async def _get_token(self) -> str:
        """Get access token from SAJ API."""
        # Always fetch a new token for each request, like the working script does
        try:
            token_url = f"{BASE_URL}{TOKEN_URL}"
            token_params = {"appId": self._app_id, "appSecret": self._app_secret}
            token_headers = {"content-language": "en_US"}

            async with async_timeout.timeout(10):
                token_resp = await self._session.get(token_url, params=token_params, headers=token_headers)
                token_json = await token_resp.json()

            if "data" not in token_json or "access_token" not in token_json["data"]:
                _LOGGER.error("Invalid token response: %s", token_json)
                return None

            self._token = token_json["data"]["access_token"]
            # Token is valid for 2 hours, but we'll refresh it after 1 hour
            self._token_expires_at = dt_util.now() + timedelta(hours=1)
            return self._token

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting access token")
            return None
        except aiohttp.ClientError as ex:
            _LOGGER.error("HTTP error getting access token: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Error getting access token: %s", ex)
            return None

    async def get_device_details(self, device_sn: str) -> Optional[Dict[str, Any]]:
        """Get device details from SAJ API."""
        token = await self._get_token()
        if not token:
            return None

        try:
            device_url = f"{BASE_URL}{DEVICE_INFO_URL}"
            device_params = {"deviceSn": device_sn}
            # Match header case exactly with the working script
            device_headers = {
                "accessToken": token,  # Note: not "AccessToken" or "access-token"
                "content-language": "en_US",
            }

            async with async_timeout.timeout(10):
                device_resp = await self._session.get(device_url, params=device_params, headers=device_headers)
                device_json = await device_resp.json()

            if device_json.get("code") != 200 or "data" not in device_json:
                _LOGGER.error("Error in device details response: %s", device_json.get("msg", "Unknown error"))
                return None

            return device_json["data"]

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting device details")
            return None
        except aiohttp.ClientError as ex:
            _LOGGER.error("HTTP error getting device details: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Error getting device details: %s", ex)
            return None

    async def get_plant_statistics(self, plant_id: str) -> Optional[Dict[str, Any]]:
        """Get plant statistics from SAJ API."""
        token = await self._get_token()
        if not token:
            return None

        try:
            now = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
            stats_url = f"{BASE_URL}{PLANT_STATS_URL}"
            stats_params = {"plantId": plant_id, "clientDate": now}
            # Include Content-Type header for plant statistics
            stats_headers = {
                "accessToken": token,
                "content-language": "en_US",
                "Content-Type": "application/json"
            }

            async with async_timeout.timeout(10):
                stats_resp = await self._session.get(stats_url, params=stats_params, headers=stats_headers)
                stats_json = await stats_resp.json()

            if stats_json.get("code") != 200 or "data" not in stats_json:
                _LOGGER.error("Error in plant statistics response: %s", stats_json.get("msg", "Unknown error"))
                return None

            return stats_json["data"]

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting plant statistics")
            return None
        except aiohttp.ClientError as ex:
            _LOGGER.error("HTTP error getting plant statistics: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Error getting plant statistics: %s", ex)
            return None

    async def get_history_data(self, device_sn: str, plant_id: str) -> Optional[Dict[str, Any]]:
        """Get historical data from SAJ API."""
        token = await self._get_token()
        if not token:
            return None

        try:
            end_time = dt_util.now()
            start_time = end_time - timedelta(minutes=10)  # Use last 10 minutes for more recent data

            start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

            history_url = f"{BASE_URL}{HISTORY_DATA_URL}"
            history_params = {
                "deviceSn": device_sn,
                "plantId": plant_id,  # Include plantId for better reliability
                "startTime": start_time_str,
                "endTime": end_time_str
            }
            
            history_headers = {
                "accessToken": token,
                "content-language": "en_US",
            }

            async with async_timeout.timeout(10):
                history_resp = await self._session.get(history_url, params=history_params, headers=history_headers)
                history_json = await history_resp.json()

            if history_json.get("code") != 200:
                _LOGGER.error("Error in history data response: %s", history_json.get("msg", "Unknown error"))
                return None
                
            if "data" not in history_json:
                # Special case: sometimes the API returns "request success" in the msg field
                # but doesn't include any data - this is normal during nighttime
                if history_json.get("msg") == "request success":
                    _LOGGER.debug("History data API returned 'request success' but no data - likely nighttime")
                    return {}
                else:
                    _LOGGER.error("No data in history data response: %s", history_json.get("msg", "Unknown error"))
                    return None

            history_data = history_json["data"]
            
            if not isinstance(history_data, list) or not history_data:
                _LOGGER.error("No history data points found in response")
                return None

            # Return the most recent data point (first in the list)
            return history_data[0]

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting history data")
            return None
        except aiohttp.ClientError as ex:
            _LOGGER.error("HTTP error getting history data: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Error getting history data: %s", ex)
            return None

    async def get_realtime_data(self, device_sn: str) -> Optional[Dict[str, Any]]:
        """Get realtime data from SAJ API."""
        token = await self._get_token()
        if not token:
            return None

        try:
            realtime_url = f"{BASE_URL}{REALTIME_DATA_URL}"
            realtime_params = {"deviceSn": device_sn}
            realtime_headers = {
                "accessToken": token,
                "content-language": "en_US",
            }

            async with async_timeout.timeout(10):
                realtime_resp = await self._session.get(realtime_url, params=realtime_params, headers=realtime_headers)
                realtime_json = await realtime_resp.json()

            if realtime_json.get("code") != 200 or "data" not in realtime_json:
                _LOGGER.error("Error in realtime data response: %s", realtime_json.get("msg", "Unknown error"))
                return None

            return realtime_json["data"]

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting realtime data")
            return None
        except aiohttp.ClientError as ex:
            _LOGGER.error("HTTP error getting realtime data: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Error getting realtime data: %s", ex)
            return None

    async def get_load_monitoring_data(self, plant_id: str) -> Optional[Dict[str, Any]]:
        """Get load monitoring data from SAJ API."""
        token = await self._get_token()
        if not token:
            return None

        try:
            # Get the current time
            now = dt_util.now()
            
            # Start time is midnight of the current day
            today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Use current time as end time to get all data for today so far
            start_time_str = today_midnight.strftime("%Y-%m-%d %H:%M:%S")
            end_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
            
            url = f"{BASE_URL}{LOAD_MONITORING_URL}"
            params = {
                "plantId": plant_id,
                "startTime": start_time_str,
                "endTime": end_time_str,
                "timeUnit": 0  # 0 for minute-level data
            }
            
            headers = {
                "accessToken": token,
                "content-language": "en_US",
            }
            
            async with async_timeout.timeout(10):
                response = await self._session.get(url, params=params, headers=headers)
                data = await response.json()
            
            if data.get("code") != 200 or "data" not in data:
                # Some systems don't have load monitoring
                if "plant has not been bound with load monitoring" in data.get("msg", ""):
                    _LOGGER.info("Plant %s does not have load monitoring", plant_id)
                else:
                    _LOGGER.error("Error in load monitoring response: %s", data.get("msg", "Unknown error"))
                return None
                
            # Extract the most recent data point
            if "dataList" in data["data"] and data["data"]["dataList"]:
                for module in data["data"]["dataList"]:
                    if "data" in module and module["data"]:
                        # Get the most recent data point
                        latest_data = module["data"][-1]
                        # Also include the total values
                        return {
                            "latest": latest_data,
                            "total": module.get("total", {}),
                            "module_sn": module.get("moduleSn", "")
                        }
            
            return None
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout getting load monitoring data")
            return None
        except aiohttp.ClientError as ex:
            _LOGGER.error("HTTP error getting load monitoring data: %s", ex)
            return None
        except Exception as ex:
            _LOGGER.error("Error getting load monitoring data: %s", ex)
            return None

    async def get_device_data(self, device: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get all data for a device."""
        device_sn = device["sn"]
        plant_id = device["plant_id"]
        device_type = device["type"]

        # Get different types of data based on device type
        plant_stats = await self.get_plant_statistics(plant_id)
        device_info = await self.get_device_details(device_sn)
        
        # Always fetch load monitoring data for solar devices (works 24/7)
        load_monitoring = None
        if device_type == DEVICE_TYPE_SOLAR:
            load_monitoring = await self.get_load_monitoring_data(plant_id)
        elif device_type != DEVICE_TYPE_BATTERY:
            # For other non-battery devices
            load_monitoring = await self.get_load_monitoring_data(plant_id)

        # For battery devices, use only realtime data
        # For solar devices, try both realtime and history data, but don't fail if they're unavailable
        history_data = None
        realtime_data = None
        
        if device_type == DEVICE_TYPE_BATTERY:
            # Battery devices are expected to be online 24/7
            # Try to get realtime data first
            realtime_data = await self.get_realtime_data(device_sn)
            
            # But even if realtime data fails, don't give up - battery devices should
            # be considered online even if the realtime API endpoint is unavailable
            if not realtime_data:
                _LOGGER.warning("Failed to get realtime data for battery device %s - will attempt to proceed anyway", device_sn)
                # Try to get history data as a fallback
                history_data = await self.get_history_data(device_sn, plant_id)
                
                # If we have device_info and plant_stats, we can still provide useful data
                if device_info and plant_stats:
                    _LOGGER.info("Battery device %s has device_info and plant_stats - continuing without realtime data", device_sn)
                else:
                    _LOGGER.error("No usable data available for battery device %s", device_sn)
                    return None
        elif device_type == DEVICE_TYPE_SOLAR:
            # Solar devices - try to get both realtime and history data
            # But don't fail if they're unavailable (nighttime operation)
            realtime_data = await self.get_realtime_data(device_sn)
            history_data = await self.get_history_data(device_sn, plant_id)
            
            # For solar devices at night, both realtime and history might be unavailable
            # That's okay, we'll use load monitoring data
            if not history_data and not realtime_data:
                _LOGGER.info("Both realtime and history data unavailable for solar device %s - likely nighttime", device_sn)
                # Make sure we have at least load monitoring data
                if not load_monitoring:
                    _LOGGER.error("No data available for solar device %s", device_sn)
                    return None
        else:
            # Other non-battery, non-solar devices use history data
            history_data = await self.get_history_data(device_sn, plant_id)
            if not history_data:
                _LOGGER.error("Failed to get history data for device %s", device_sn)
                return None

        # Process data based on device type and available data
        # For solar, use realtime data if available, then history data, then load monitoring
        is_realtime = False
        data_to_process = None
        
        if device_type == DEVICE_TYPE_BATTERY:
            is_realtime = True
            data_to_process = realtime_data
        elif device_type == DEVICE_TYPE_SOLAR:
            # For solar, prioritize data sources
            if realtime_data and realtime_data.get("isOnline") == "1":
                is_realtime = True
                data_to_process = realtime_data
                _LOGGER.debug("Using realtime data for solar device %s", device_sn)
            elif history_data:
                is_realtime = False
                data_to_process = history_data
                _LOGGER.debug("Using history data for solar device %s", device_sn)
            else:
                # No realtime or history data available (nighttime)
                # We'll use an empty dict and rely on load monitoring data
                is_realtime = False
                data_to_process = {}
                _LOGGER.debug("Using empty data for solar device %s (nighttime)", device_sn)
        else:
            # Other device types
            is_realtime = False
            data_to_process = history_data
        
        processed_data = self._process_device_data(
            data_to_process, 
            plant_stats, 
            device_type, 
            is_realtime=is_realtime,
            load_monitoring=load_monitoring  # Pass load monitoring data for nighttime operation
        )
        
        # Combine all data into a single dictionary
        return {
            "device_info": device_info,
            "plant_stats": plant_stats,
            "history_data": history_data,
            "realtime_data": realtime_data,
            "load_monitoring": load_monitoring,
            "device_type": device_type,
            "processed_data": processed_data,
        }
    
    def _process_device_data(self, data, plant_stats, device_type, is_realtime=False, load_monitoring=None):
        """Process device data to create calculated fields."""
        processed = {}
        
        if not data and device_type != DEVICE_TYPE_SOLAR:
            return processed

        if is_realtime and device_type == DEVICE_TYPE_BATTERY:
            # Use realtime data fields for battery devices
            try:
                # Log device type
                _LOGGER.debug("Device type: battery")
                
                # Grid-related data
                _LOGGER.debug("--- GRID DATA ---")
                _LOGGER.debug("Realtime data sysGridPowerWatt: %s", data.get('sysGridPowerWatt'))
                _LOGGER.debug("Realtime data gridDirection: %s", data.get('gridDirection'))
                _LOGGER.debug("Realtime data todaySellEnergy: %s", data.get('todaySellEnergy'))
                _LOGGER.debug("Realtime data todayFeedInEnergy: %s", data.get('todayFeedInEnergy'))
                
                # Battery-related data
                _LOGGER.debug("--- BATTERY DATA ---")
                _LOGGER.debug("Realtime data batPower: %s", data.get('batPower'))
                _LOGGER.debug("Realtime data batEnergyPercent: %s", data.get('batEnergyPercent'))
                _LOGGER.debug("Realtime data batteryDirection: %s", data.get('batteryDirection'))
                _LOGGER.debug("Realtime data todayBatChgEnergy: %s", data.get('todayBatChgEnergy'))
                _LOGGER.debug("Realtime data todayBatDisEnergy: %s", data.get('todayBatDisEnergy'))
                _LOGGER.debug("Realtime data totalBatChgEnergy: %s", data.get('totalBatChgEnergy'))
                _LOGGER.debug("Realtime data totalBatDisEnergy: %s", data.get('totalBatDisEnergy'))
                
                # Load-related data
                _LOGGER.debug("--- LOAD DATA ---")
                _LOGGER.debug("Realtime data sysTotalLoadWatt: %s", data.get('sysTotalLoadWatt'))
                _LOGGER.debug("Realtime data todayLoadEnergy: %s", data.get('todayLoadEnergy'))
                
                # PV-related data
                _LOGGER.debug("--- PV DATA ---")
                _LOGGER.debug("Realtime data todayPvEnergy: %s", data.get('todayPvEnergy'))
                _LOGGER.debug("Realtime data totalPvEnergy: %s", data.get('totalPvEnergy'))
                _LOGGER.debug("Realtime data totalPVPower: %s", data.get('totalPVPower'))
                
                # Temperature data
                _LOGGER.debug("--- TEMPERATURE DATA ---")
                _LOGGER.debug("Realtime data batTempC: %s", data.get('batTempC'))
                _LOGGER.debug("Realtime data sinkTempC: %s", data.get('sinkTempC'))
                
                # Operating mode data
                _LOGGER.debug("--- OPERATING MODE DATA ---")
                _LOGGER.debug("Realtime data mpvMode: %s", data.get('mpvMode'))
                
                # Additional energy data
                _LOGGER.debug("--- ADDITIONAL ENERGY DATA ---")
                _LOGGER.debug("Realtime data totalSellEnergy: %s", data.get('totalSellEnergy'))
                _LOGGER.debug("Realtime data totalFeedInEnergy: %s", data.get('totalFeedInEnergy'))
                _LOGGER.debug("Realtime data totalTotalLoadEnergy: %s", data.get('totalTotalLoadEnergy'))

                # Grid power from sysGridPowerWatt
                grid_power = float(data.get('sysGridPowerWatt', 0))
                processed["grid_power_abs"] = abs(grid_power)
                # Grid direction based on gridDirection (1 for exporting/selling, -1 for importing/feeding in)
                grid_direction_value = int(data.get('gridDirection', 0))
                grid_direction = "exporting" if grid_direction_value == 1 else "importing" if grid_direction_value == -1 else "idle"
                processed["grid_status_calculated"] = grid_direction

                # Home load from sysTotalLoadWatt
                processed["home_load_power"] = float(data.get('sysTotalLoadWatt', 0))
                
                # Battery data
                bat_power = float(data.get('batPower', 0))
                bat_level = float(data.get('batEnergyPercent', 0))
                processed["battery_level"] = bat_level
                processed["battery_power_abs"] = abs(bat_power)
                
                # Battery status from batteryDirection (0 for idle)
                bat_direction = int(data.get('batteryDirection', 0))
                if bat_direction == 0:
                    bat_status = "Standby"
                else:
                    bat_status = "Discharging" if bat_power > 0 else "Charging"
                processed["battery_status_calculated"] = bat_status
                
                # Temperature values
                if "batTempC" in data and data["batTempC"] != "0":
                    processed["battery_temp"] = float(data["batTempC"])
                if "sinkTempC" in data and data["sinkTempC"] != "0":
                    processed["sink_temp"] = float(data["sinkTempC"])

                # Energy values
                processed["today_battery_charge"] = float(data.get('todayBatChgEnergy', 0))
                processed["today_battery_discharge"] = float(data.get('todayBatDisEnergy', 0))
                
                # Store total battery energy values
                if 'totalBatChgEnergy' in data:
                    processed["total_battery_charge"] = float(data.get('totalBatChgEnergy', 0))
                if 'totalBatDisEnergy' in data:
                    processed["total_battery_discharge"] = float(data.get('totalBatDisEnergy', 0))
                
                processed["today_load_energy"] = float(data.get('todayLoadEnergy', 0))
                processed["today_pv_energy"] = float(data.get('todayPvEnergy', 0))
                processed["total_pv_energy"] = float(data.get('totalPvEnergy', 0))
                
                # Process current PV power from totalPVPower field
                if 'totalPVPower' in data:
                    try:
                        processed["total_pv_power_calculated"] = float(data.get('totalPVPower', 0))
                    except (ValueError, TypeError):
                        _LOGGER.warning("Could not convert totalPVPower value to float: %s", data.get('totalPVPower'))
                
                # Grid energy exchange values
                processed["today_grid_export_energy"] = float(data.get('todaySellEnergy', 0))
                processed["today_grid_import_energy"] = float(data.get('todayFeedInEnergy', 0))
                
                # Add total grid export energy if available
                if 'totalSellEnergy' in data:
                    try:
                        processed["total_grid_export"] = float(data.get('totalSellEnergy', 0))
                    except (ValueError, TypeError):
                        _LOGGER.warning("Could not convert totalSellEnergy value to float: %s", data.get('totalSellEnergy'))
                
                # Add total grid import energy if available
                if 'totalFeedInEnergy' in data:
                    try:
                        processed["total_grid_import"] = float(data.get('totalFeedInEnergy', 0))
                    except (ValueError, TypeError):
                        _LOGGER.warning("Could not convert totalFeedInEnergy value to float: %s", data.get('totalFeedInEnergy'))
                
                # Add total load energy if available
                if 'totalTotalLoadEnergy' in data:
                    try:
                        processed["total_load_energy"] = float(data.get('totalTotalLoadEnergy', 0))
                    except (ValueError, TypeError):
                        _LOGGER.warning("Could not convert totalTotalLoadEnergy value to float: %s", data.get('totalTotalLoadEnergy'))
                
                # Add operating mode/status from mpvMode if available
                if 'mpvMode' in data:
                    try:
                        mpv_mode = int(data.get('mpvMode', 0))
                        processed["operating_mode"] = mpv_mode
                        processed["operating_status"] = mpv_mode
                    except (ValueError, TypeError):
                        _LOGGER.warning("Could not convert mpvMode value to int: %s", data.get('mpvMode'))
                
                # Calculate estimated annual production and savings
                if 'todayPvEnergy' in data:
                    try:
                        today_energy = float(data.get('todayPvEnergy', 0))
                        days_passed = dt_util.now().timetuple().tm_yday  # Day of the year
                        if days_passed > 0:
                            processed["estimated_annual_production"] = today_energy / days_passed * 365
                            # Estimate financial savings (using $0.15/kWh as an example)
                            processed["estimated_annual_savings"] = processed["estimated_annual_production"] * 0.15
                    except (ValueError, TypeError, ZeroDivisionError):
                        pass

                return processed

            except (ValueError, TypeError) as ex:
                _LOGGER.error("Error processing realtime data: %s", ex)
                return processed
            
        # For solar devices, process data with special handling for nighttime
        if device_type == DEVICE_TYPE_SOLAR:
            # Check if we're likely in nighttime mode (empty data)
            is_nighttime = not data or (is_realtime and data.get("isOnline") != "1")
            
            if is_nighttime:
                _LOGGER.debug("Solar inverter appears to be offline (nighttime)")
            
            # Process PV data - set to 0 during nighttime
            _LOGGER.debug("--- PV DATA ---")
            if is_nighttime:
                # During nighttime, all PV values are 0
                processed["total_pv_power_calculated"] = 0
                for i in range(1, 3):  # Just PV1 and PV2
                    # Set power, voltage, and current to 0 for PV1 and PV2
                    processed[f"pv{i}_power"] = 0
                    processed[f"pv{i}_voltage"] = 0
                    processed[f"pv{i}_current"] = 0
                _LOGGER.debug("Nighttime operation - PV1 and PV2 values (power, voltage, current) set to 0")
                
                # Set grid phase values to 0 during nighttime
                for phase in ["r", "s", "t"]:
                    processed[f"{phase}_phase_power"] = 0
                    processed[f"{phase}_phase_voltage"] = 0
                    processed[f"{phase}_phase_current"] = 0
                    processed[f"{phase}_phase_frequency"] = 0
                _LOGGER.debug("Nighttime operation - Grid phase values (power, voltage, current, frequency) set to 0")
                
                # Set default operating mode during nighttime
                processed["operating_mode"] = 0
                processed["operating_status"] = 1  # 1 = Waiting (Standby)
                _LOGGER.debug("Nighttime operation - Operating mode set to 0, status set to 1 (Standby)")
            else:
                # Normal daytime operation - process PV data
                total_pv_power = 0
                for i in range(1, 17):  # Check all possible PV inputs
                    pv_power_key = f"pv{i}power"
                    if pv_power_key in data and data[pv_power_key]:
                        _LOGGER.debug("%s data %s: %s", 
                                    "Realtime" if is_realtime else "History", 
                                    pv_power_key, 
                                    data.get(pv_power_key))
                        try:
                            pv_power = float(data[pv_power_key])
                            total_pv_power += pv_power
                            processed[f"pv{i}_power"] = pv_power
                        except (ValueError, TypeError):
                            pass
                
                # Check if totalPVPower is available in the data
                if "totalPVPower" in data:
                    _LOGGER.debug("%s data totalPVPower: %s", 
                                "Realtime" if is_realtime else "History", 
                                data.get("totalPVPower"))
                    
                    # Try to use totalPVPower from data if it's not zero
                    try:
                        reported_total = float(data.get("totalPVPower", 0))
                        if reported_total > 0:
                            processed["total_pv_power_calculated"] = reported_total
                        else:
                            # If totalPVPower is 0 but we calculated a non-zero sum, use our calculation
                            processed["total_pv_power_calculated"] = total_pv_power if total_pv_power > 0 else 0
                    except (ValueError, TypeError):
                        # If conversion fails, use our calculated sum
                        processed["total_pv_power_calculated"] = total_pv_power if total_pv_power > 0 else 0
                else:
                    # If totalPVPower is not in the data, use our calculated sum
                    processed["total_pv_power_calculated"] = total_pv_power if total_pv_power > 0 else 0
            
            # Process grid data - prioritize load monitoring data
            _LOGGER.debug("--- GRID DATA ---")
            if load_monitoring:
                # Use load monitoring data for grid power (works 24/7)
                latest = load_monitoring.get("latest", {})
                if "buyPower" in latest and "sellPower" in latest:
                    try:
                        buy_power = float(latest.get("buyPower", 0))
                        sell_power = float(latest.get("sellPower", 0))
                        
                        # Net grid power (positive = importing, negative = exporting)
                        grid_power = buy_power - sell_power
                        
                        _LOGGER.debug("Load monitoring buyPower: %s", buy_power)
                        _LOGGER.debug("Load monitoring sellPower: %s", sell_power)
                        _LOGGER.debug("Calculated grid power: %s", grid_power)
                        
                        grid_direction = "exporting" if grid_power < 0 else "importing" if grid_power > 0 else "idle"
                        processed["grid_status_calculated"] = grid_direction
                        processed["grid_power_abs"] = abs(grid_power)
                    except (ValueError, TypeError):
                        pass
            elif not is_nighttime:
                # Fall back to realtime/history data if load monitoring is unavailable.
                # For R6 solar devices the API reports totalGridPowerWatt as a positive
                # magnitude and gridDirection=-1 when exporting (matching the SAJ app).
                _LOGGER.debug("%s data totalGridPowerWatt: %s",
                            "Realtime" if is_realtime else "History",
                            data.get('totalGridPowerWatt'))
                try:
                    total_grid_power = abs(float(data.get('totalGridPowerWatt', 0) or 0))
                    sys_grid_power = abs(float(data.get('sysGridPowerWatt', 0) or 0))
                    # SAJ R6 can report totalGridPowerWatt as per-phase/partial (~4 kW)
                    # while the app's grid bubble uses sysGridPowerWatt/whole-site export
                    # (~13 kW). Use the larger magnitude for power-balance load estimates.
                    grid_power = max(total_grid_power, sys_grid_power)
                    grid_direction_value = int(float(data.get('gridDirection', 0)))
                    if grid_direction_value == -1:
                        grid_direction = "exporting"
                    elif grid_direction_value == 1:
                        grid_direction = "importing"
                    else:
                        grid_direction = "exporting" if float(data.get('totalGridPowerWatt', 0) or 0) < 0 else "importing" if grid_power > 0 else "idle"
                    processed["grid_status_calculated"] = grid_direction
                    processed["grid_power_abs"] = grid_power
                except (ValueError, TypeError):
                    pass

            # Process home load power - prioritize load monitoring data
            _LOGGER.debug("--- LOAD DATA ---")
            if load_monitoring:
                # Use load monitoring data for home load (works 24/7)
                latest = load_monitoring.get("latest", {})
                if "loadPower" in latest:
                    try:
                        load_power = float(latest.get("loadPower", 0))
                        _LOGGER.debug("Load monitoring loadPower: %s", load_power)
                        processed["home_load_power"] = load_power
                    except (ValueError, TypeError):
                        pass
            elif not is_nighttime:
                # SAJ R6 realtime/history often leaves totalLoadPowerWatt/sysTotalLoadWatt
                # at 0 even though the app displays Total load as PV power minus exported
                # grid power. Use the explicit load field if non-zero; otherwise estimate
                # instantaneous load from the power balance.
                try:
                    explicit_load = float(data.get("totalLoadPowerWatt") or data.get("sysTotalLoadWatt") or 0)
                    if explicit_load > 0:
                        processed["home_load_power"] = explicit_load
                    else:
                        pv_power = float(data.get("totalPVPower", processed.get("total_pv_power_calculated", 0)) or 0)
                        grid_abs = float(processed.get("grid_power_abs", abs(float(data.get("totalGridPowerWatt", 0) or 0))))
                        grid_status = processed.get("grid_status_calculated")
                        if grid_status == "exporting":
                            processed["home_load_power"] = max(pv_power - grid_abs, 0)
                            processed["home_load_power_estimated"] = True
                        elif grid_status == "importing":
                            processed["home_load_power"] = max(pv_power + grid_abs, 0)
                            processed["home_load_power_estimated"] = True
                except (ValueError, TypeError):
                    pass
            
            # Process phase data if available (only during daytime)
            if not is_nighttime:
                _LOGGER.debug("--- PHASE DATA ---")
                try:
                    total_phase_power = 0
                    for phase in ["r", "s", "t"]:
                        phase_power_key = f"{phase}GridPowerWatt"
                        if phase_power_key in data and data[phase_power_key]:
                            _LOGGER.debug("%s data %s: %s", 
                                        "Realtime" if is_realtime else "History", 
                                        phase_power_key, 
                                        data.get(phase_power_key))
                            phase_power = float(data[phase_power_key])
                            total_phase_power += phase_power
                            processed[f"{phase}_phase_power"] = phase_power
                    processed["total_phase_power"] = total_phase_power
                except (ValueError, TypeError):
                    pass
                
            # Process temperature data (only during daytime)
            if not is_nighttime:
                _LOGGER.debug("--- TEMPERATURE DATA ---")
                _LOGGER.debug("%s data invTempC: %s", 
                            "Realtime" if is_realtime else "History", 
                            data.get("invTempC"))
                _LOGGER.debug("%s data sinkTempC: %s", 
                            "Realtime" if is_realtime else "History", 
                            data.get("sinkTempC"))
                try:
                    if "invTempC" in data and data["invTempC"]:
                        processed["inverter_temp"] = float(data["invTempC"])
                    if "sinkTempC" in data and data["sinkTempC"]:
                        processed["sink_temp"] = float(data["sinkTempC"])
                except (ValueError, TypeError):
                    pass
            
            # Process plant statistics data (always available)
            if plant_stats:
                _LOGGER.debug("--- PLANT STATISTICS ---")
                _LOGGER.debug("Plant stats totalReduceCo2: %s", plant_stats.get("totalReduceCo2"))
                _LOGGER.debug("Plant stats totalPlantTreeNum: %s", plant_stats.get("totalPlantTreeNum"))
                _LOGGER.debug("Plant stats yearPvEnergy: %s", plant_stats.get("yearPvEnergy"))
                try:
                    # Environmental impact
                    if "totalReduceCo2" in plant_stats:
                        processed["co2_reduction"] = float(plant_stats["totalReduceCo2"])
                    if "totalPlantTreeNum" in plant_stats:
                        processed["equivalent_trees"] = float(plant_stats["totalPlantTreeNum"])
                        
                    # Annual projections
                    if "yearPvEnergy" in plant_stats:
                        year_energy = float(plant_stats["yearPvEnergy"])
                        days_passed = dt_util.now().timetuple().tm_yday  # Day of the year
                        if days_passed > 0:
                            processed["estimated_annual_production"] = year_energy / days_passed * 365
                            # Estimate financial savings (using $0.15/kWh as an example)
                            processed["estimated_annual_savings"] = processed["estimated_annual_production"] * 0.15
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # Process energy data - set to 0 during nighttime for today's values
            if is_nighttime:
                processed["today_pv_energy"] = 0
            elif "todayPvEnergy" in data:
                try:
                    processed["today_pv_energy"] = float(data["todayPvEnergy"])
                except (ValueError, TypeError):
                    processed["today_pv_energy"] = 0
            
            # Total energy values should still be available from plant stats
            if "totalPvEnergy" in data:
                try:
                    processed["total_pv_energy"] = float(data["totalPvEnergy"])
                except (ValueError, TypeError):
                    pass
            elif plant_stats and "totalPvEnergy" in plant_stats:
                try:
                    processed["total_pv_energy"] = float(plant_stats["totalPvEnergy"])
                except (ValueError, TypeError):
                    pass
            
            # Process grid export/import data
            if is_nighttime:
                processed["today_grid_export_energy"] = 0
            elif "todaySellEnergy" in data:
                try:
                    processed["today_grid_export_energy"] = float(data["todaySellEnergy"])
                except (ValueError, TypeError):
                    processed["today_grid_export_energy"] = 0
            
            # Total grid export should still be available
            if "totalSellEnergy" in data:
                try:
                    processed["total_grid_export"] = float(data["totalSellEnergy"])
                except (ValueError, TypeError):
                    pass
            elif plant_stats and "totalSellEnergy" in plant_stats:
                try:
                    processed["total_grid_export"] = float(plant_stats["totalSellEnergy"])
                except (ValueError, TypeError):
                    pass
            
            # Process load monitoring energy data (works 24/7)
            if load_monitoring:
                total_values = load_monitoring.get("total", {})
                
                # Log the energy values
                _LOGGER.debug("Load monitoring buyEnergy: %s", total_values.get("buyEnergy"))
                _LOGGER.debug("Load monitoring sellEnergy: %s", total_values.get("sellEnergy"))
                _LOGGER.debug("Load monitoring pvEnergy: %s", total_values.get("pvEnergy"))
                _LOGGER.debug("Load monitoring loadEnergy: %s", total_values.get("loadEnergy"))
                
                if "pvEnergy" in total_values:
                    try:
                        pv_energy = float(total_values["pvEnergy"])
                        processed["today_pv_energy"] = pv_energy
                        _LOGGER.debug("Stored load monitoring pvEnergy in processed data: %s", pv_energy)
                    except (ValueError, TypeError):
                        pass
                
                if "loadEnergy" in total_values:
                    try:
                        processed["total_load_energy"] = float(total_values["loadEnergy"])
                    except (ValueError, TypeError):
                        pass
                
                if "buyEnergy" in total_values:
                    try:
                        processed["total_grid_import"] = float(total_values["buyEnergy"])
                        processed["today_grid_import_energy"] = float(total_values["buyEnergy"])
                    except (ValueError, TypeError):
                        pass
                
                if "sellEnergy" in total_values:
                    try:
                        # Double-check this against total_grid_export
                        sell_energy = float(total_values["sellEnergy"])
                        if "total_grid_export" not in processed:
                            processed["total_grid_export"] = sell_energy
                        processed["today_grid_export_energy"] = sell_energy
                    except (ValueError, TypeError):
                        pass
            
            return processed
        # Battery status (for battery devices)
        if device_type == DEVICE_TYPE_BATTERY:
            _LOGGER.debug("--- BATTERY DATA ---")
            _LOGGER.debug("History data batPower: %s", data.get("batPower"))
            _LOGGER.debug("History data batEnergyPercent: %s", data.get("batEnergyPercent"))
            try:
                bat_power = float(data.get("batPower", 0))
                if bat_power > 0:
                    bat_status = "Discharging"
                elif bat_power < 0:
                    bat_status = "Charging"
                else:
                    bat_status = "Standby"
                processed["battery_status_calculated"] = bat_status
                processed["battery_power_abs"] = abs(bat_power)
            except (ValueError, TypeError):
                pass
                
        # Device type specific processing
        if device_type == DEVICE_TYPE_SOLAR:
            # For R6: Calculate combined phase values
            _LOGGER.debug("--- PHASE DATA ---")
            try:
                total_phase_power = 0
                for phase in ["r", "s", "t"]:
                    phase_power_key = f"{phase}GridPowerWatt"
                    if phase_power_key in data and data[phase_power_key]:
                        _LOGGER.debug("History data %s: %s", phase_power_key, data.get(phase_power_key))
                        phase_power = float(data[phase_power_key])
                        total_phase_power += phase_power
                        processed[f"{phase}_phase_power"] = phase_power
                processed["total_phase_power"] = total_phase_power
            except (ValueError, TypeError):
                pass
                
        # Temperature values
        _LOGGER.debug("--- TEMPERATURE DATA ---")
        _LOGGER.debug("History data invTempC: %s", data.get("invTempC"))
        _LOGGER.debug("History data sinkTempC: %s", data.get("sinkTempC"))
        try:
            if "invTempC" in data and data["invTempC"]:
                processed["inverter_temp"] = float(data["invTempC"])
            if "sinkTempC" in data and data["sinkTempC"]:
                processed["sink_temp"] = float(data["sinkTempC"])
        except (ValueError, TypeError):
            pass
            
        # Process plant statistics data
        if plant_stats:
            _LOGGER.debug("--- PLANT STATISTICS ---")
            _LOGGER.debug("Plant stats totalReduceCo2: %s", plant_stats.get("totalReduceCo2"))
            _LOGGER.debug("Plant stats totalPlantTreeNum: %s", plant_stats.get("totalPlantTreeNum"))
            _LOGGER.debug("Plant stats yearPvEnergy: %s", plant_stats.get("yearPvEnergy"))
            try:
                # Environmental impact
                if "totalReduceCo2" in plant_stats:
                    processed["co2_reduction"] = float(plant_stats["totalReduceCo2"])
                if "totalPlantTreeNum" in plant_stats:
                    processed["equivalent_trees"] = float(plant_stats["totalPlantTreeNum"])
                    
                # Annual projections
                if "yearPvEnergy" in plant_stats:
                    year_energy = float(plant_stats["yearPvEnergy"])
                    days_passed = dt_util.now().timetuple().tm_yday  # Day of the year
                    if days_passed > 0:
                        processed["estimated_annual_production"] = year_energy / days_passed * 365
                        # Estimate financial savings (using $0.15/kWh as an example)
                        processed["estimated_annual_savings"] = processed["estimated_annual_production"] * 0.15
            except (ValueError, TypeError, ZeroDivisionError):
                pass
                
        return processed
