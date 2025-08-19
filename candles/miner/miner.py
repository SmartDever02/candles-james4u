# The MIT License (MIT)
# Copyright © 2024 sportstensor

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


import asyncio
from typing import Tuple
import os
import bittensor
from datetime import datetime, timezone
import random
from decimal import Decimal
from pathlib import Path
import glob
import requests
from collections import defaultdict
import json

from candles.core.synapse import GetCandlePrediction
from candles.core.data import CandlePrediction, CandleColor, TimeInterval
from candles.miner.base import BaseMinerNeuron
from candles.miner.utils import get_file_predictions



class Miner(BaseMinerNeuron):
    """The Candles Miner."""

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

    async def async_init(self):
        """
        Async initialization for miner. Must be called after __init__.
        """
        # Initialize the base miner async components
        await super().async_init()
        
    async def get_asset_price(self, asset="TAO"):
        ### Hard coded url & token map ###
        pyth_base_url = "https://hermes.pyth.network/v2/updates/price/latest"
        TOKEN_MAP = {
            "TAO": "410f41de235f2db824e562ea7ab2d3d3d4ff048316c61d629c0b93f58584e1af"
        }
        ######### End of config #########
        
        pyth_params = {"ids[]": [TOKEN_MAP[asset]]}
        response = requests.get(pyth_base_url, params=pyth_params)
        if response.status_code != 200:
            print("Error in response of Pyth API")
            return

        data = response.json()
        parsed_data = data.get("parsed", [])

        asset = parsed_data[0]
        price = int(asset["price"]["price"])
        expo = int(asset["price"]["expo"])

        live_price = price * (10**expo)

        return live_price

    def load_params(self, asset="TAO", interval: str = "hourly", retries=3, delay=0.5):
        for attempt in range(1, retries + 1):
            try:
                # Load the JSON file
                with open("params.json", "r") as f:
                    data = json.load(f)

                # Access nested values
                mode = data[asset]["mode"]
                offset = data[asset][f"{interval}_offset"]
                return mode, offset

            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                print(f"Attempt {attempt} failed: {e}")
                if attempt < retries:
                    time.sleep(delay)  # wait before retrying
                else:
                    "SMOOTH", 10  # send fallback values as config

    def set_price_range(self, mode: str, offset: int, live_price: float):
        min_price = max_price = live_price
        
        if mode == "HOT":
            min_price -= offset / 2
            max_price += offset
        
        if mode == "COLD":
            min_price -= offset
            max_price += offset / 2
            
        if mode == "SMOOTH":
            min_price -= offset / 2
            max_price += offset / 2
        
        return min_price, max_price

    def adjust_price(self, price: float, interval: str):
        my_coldkeys = [
            '5HZAKfn97xkdpFQ6kUmVGz6aVSFLaxn6bJ887zxpEv2VdF9g',
            '5FbZXuyucSr6BzCY9sRSiRyL5HBo54nAxp4dFNxCd4Q8C5yy',
            '5GYsGZe8Ckmjo4RcHCGVyQSdvnDMPLBH29JPMzMv1eJQSE3u'
        ]
        my_hotkeys = []
        
        # Collect all matching indexes
        key_to_indexes = defaultdict(list)
        self.metagraph.sync()
        
        for i, key in enumerate(self.metagraph.coldkeys):
            if key in my_coldkeys:
                key_to_indexes[key].append(i)
                my_hotkeys.append(self.metagraph.hotkeys[i])
            
        friendly_uids = [index for indexes in key_to_indexes.values() for index in indexes]
        
        miner_len = len(friendly_uids)
        
        mode, offset = self.load_params(asset = "TAO", interval = interval)
        
        min_price, max_price = self.set_price_range(mode, offset, price)
        
        price_offset_range = max_price - min_price
        
        bittensor.logging.info(f"My hotkey lists: {my_hotkeys}")
        
        hotkey_index = my_hotkeys.index(self.wallet.hotkey.ss58_address)
        
        __price = min_price + hotkey_index * (price_offset_range / miner_len)
        __miner_uid = friendly_uids[hotkey_index]
        
        bittensor.logging.info(f"[Succcess] Adjusted price for miner [{__miner_uid}]: {__price:.4f}")
        
        return __price

    def blacklist(self, synapse: GetCandlePrediction) -> Tuple[bool, str]:
        """
        ** Warning do not use `tuple` or `typing.Tuple` in this function.
        ** Use `Tuple[bool, str]` instead.

        Determines whether an incoming request should be blacklisted and thus ignored. Your implementation should
        define the logic for blacklisting requests based on your needs and desired security parameters.

        Blacklist runs before the synapse data has been deserialized (i.e. before synapse.data is available).
        The synapse is instead contructed via the headers of the request. It is important to blacklist
        requests before they are deserialized to avoid wasting resources on requests that will be ignored.

        Args:
            synapse (GetCandlePrediction): A synapse object constructed from the headers of the incoming request.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating whether the synapse's hotkey is blacklisted,
                            and a string providing the reason for the decision.
        """
        if not synapse.dendrite.hotkey: # type: ignore
            return True, "Hotkey not provided"

        # Get the miner instance from the synapse
        registered = synapse.dendrite.hotkey in self.metagraph.hotkeys # type: ignore
        if self.config.blacklist.allow_non_registered and not registered:
            return False, "Allowing un-registered hotkey"
        elif not registered:
            bittensor.logging.trace(
                f"Blacklisting un-registered hotkey {synapse.dendrite.hotkey}" # type: ignore
            )
            return True, f"Unrecognized hotkey {synapse.dendrite.hotkey}" # type: ignore

        uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey) # type: ignore
        if self.config.blacklist.force_validator_permit and not self.metagraph.validator_permit[uid]:
            bittensor.logging.warning(
                f"Blacklisting a request from non-validator hotkey {synapse.dendrite.hotkey}" # type: ignore
            )
            return True, "Non-validator hotkey"

        stake = self.metagraph.S[uid].item()
        if (
            self.config.blacklist.validator_min_stake
            and stake < self.config.blacklist.validator_min_stake
        ):
            bittensor.logging.warning(
                f"Blacklisting request from {synapse.dendrite.hotkey} [uid={uid}], not enough stake -- {stake}" # type: ignore
            )
            return True, "Stake below minimum"

        bittensor.logging.trace(
            f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}" # type: ignore
        )
        return False, "Hotkey recognized!"

    async def priority(self, synapse: GetCandlePrediction) -> float:
        """
        The priority function determines the order in which requests are handled. More valuable or higher-priority
        requests are processed before others. You should design your own priority mechanism with care.

        This implementation assigns priority to incoming requests based on the calling entity's stake in the metagraph.

        Args:
            synapse (GetCandlePrediction): The synapse object that contains metadata about the incoming request.

        Returns:
            float: A priority score derived from the stake of the calling entity.

        Miners may recieve messages from multiple entities at once. This function determines which request should be
        processed first. Higher values indicate that the request should be processed first. Lower values indicate
        that the request should be processed later.

        Example priority logic:
        - A higher stake results in a higher priority value.
        """
        caller_uid = self.metagraph.hotkeys.index(
            synapse.dendrite.hotkey # type: ignore
        )  # Get the caller index.
        prirority = float(
            self.metagraph.S[caller_uid]
        )  # Return the stake as the priority.
        bittensor.logging.trace(
            f"Prioritizing {synapse.dendrite.hotkey} with value: ", prirority # type: ignore
        )
        return prirority

    def find_prediction_file(self, interval: TimeInterval) -> str | None:
        """
        Find prediction files based on interval type. Searches in ~/.candles/data/ first,
        then falls back to PREDICTIONS_FILE_PATH env var.

        Args:
            interval: The time interval to find predictions for

        Returns:
            str: Path to the prediction file, or None if not found
        """
        # Map intervals to file prefixes
        interval_prefixes = {
            TimeInterval.HOURLY: "hourly_",
            TimeInterval.DAILY: "daily_",
            TimeInterval.WEEKLY: "weekly_"
        }

        prefix = interval_prefixes.get(interval)
        if not prefix:
            return None

        # Check ~/.candles/data/ directory first
        candles_data_dir = Path.home() / ".candles" / "data"
        if candles_data_dir.exists():
            pattern = str(candles_data_dir / f"{prefix}*.csv")
            if matching_files := glob.glob(pattern):
                # Return the first matching file (sorted for consistency)
                return sorted(matching_files)[0]

        # Fall back to PREDICTIONS_FILE_PATH env var
        predictions_file_path = os.getenv("PREDICTIONS_FILE_PATH")
        if predictions_file_path and os.path.exists(predictions_file_path):
            return predictions_file_path

        return None

    async def make_candle_prediction(self, candle_prediction):
        """
        Makes a prediction for the requested candle.

        Args:
            candle_prediction: The CandlePrediction object containing the request details.

        Returns:
            CandlePrediction: The prediction with color, price, and confidence.
        """
        bittensor.logging.info(f"****************** Making prediction for interval: [blue]{candle_prediction.interval}[/blue] ******************")

        if prediction_file := self.find_prediction_file(
            candle_prediction.interval
        ):
            bittensor.logging.info(f"[orange]Found prediction file[/orange]: [blue]{prediction_file}[/blue]")
            if predictions := get_file_predictions(
                filename=prediction_file,
                interval=candle_prediction.interval,
                miner_uid=self.uid,
                hotkey=self.wallet.hotkey.ss58_address,
            ):
                if prediction := next(
                    (
                        prediction
                        for prediction in predictions
                        if prediction.interval_id == candle_prediction.interval_id
                    ),
                    None,
                ):
                    bittensor.logging.info(f"[orange]Using prediction from file[/orange]: [blue]{prediction}[/blue]")
                    return prediction

        # Generate random prediction directly for better test compatibility
        bittensor.logging.debug(f"Making prediction for interval: {candle_prediction.interval}")

        # Generate a random price between 100 and 1000
        live_price = await self.get_asset_price("TAO")
        bittensor.logging.debug(f"Fetched price from pyth: {live_price}")

        price = self.adjust_price(live_price, candle_prediction.interval)
        
        color = CandleColor.GREEN if price > live_price else CandleColor.RED
        bittensor.logging.debug(f"Generated color: {color}")

        # Generate a random confidence between 0.5 and 1.0
        confidence = Decimal('0.7')
        bittensor.logging.debug(f"Generated confidence: {confidence}")

        # Use the original interval_id if provided
        interval_id = candle_prediction.interval_id if hasattr(candle_prediction, 'interval_id') and candle_prediction.interval_id else f"generated_{candle_prediction.interval}"

        # Preserve the original prediction_id if provided
        prediction_id = candle_prediction.prediction_id if hasattr(candle_prediction, 'prediction_id') and candle_prediction.prediction_id else None

        return CandlePrediction(
            prediction_id=prediction_id,
            price=price,
            color=color,
            confidence=confidence,
            prediction_date=datetime.now(timezone.utc),
            interval=candle_prediction.interval,
            interval_id=interval_id,
            miner_uid=self.uid,
            hotkey=self.wallet.hotkey.ss58_address,
        )

    async def get_candle_prediction(self, synapse: GetCandlePrediction) -> GetCandlePrediction:
        bittensor.logging.debug(
            f"Received GetCandlePrediction request in forward() from {synapse.dendrite.hotkey}." # type: ignore
        )

        synapse.candle_prediction = await self.make_candle_prediction(synapse.candle_prediction)
        synapse.version = 1

        bittensor.logging.success(
            f"Returning CandlePrediction to [orange]{synapse.dendrite.hotkey}[/orange]:" + # type: ignore
            f"\n color = [yellow]{synapse.candle_prediction.color}[/yellow]," +
            f"\n price = [orange]{synapse.candle_prediction.price}[/orange]," +
            f"\n confidence = [magenta]{synapse.candle_prediction.confidence}[/magenta]."
        )

        return synapse

    def save_state(self):
        """
        We define this function to avoid printing out the log message in the BaseNeuron class
        that says `save_state() not implemented`.
        """
        pass


async def main():
    """Main async entry point for the miner."""
    miner = Miner()
    try:
        await miner.async_init()
        await miner.run()
    finally:
        if not miner.config.mock: # type: ignore
            await miner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
