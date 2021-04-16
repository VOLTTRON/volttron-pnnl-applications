from day_ahead_auction import DayAheadAuction
from datetime import datetime, timedelta
from TransactiveNode import TransactiveNode
from market_types import MarketTypes


def test_spawn_markets():
    print('Running test_spawn_markets()')
    time = datetime(year=2020, month=8, day=18, hour=11)
    test_node = TransactiveNode()
    prior_da_auction = DayAheadAuction()
    prior_da_auction.marketClearingInterval = timedelta(hours=24)
    prior_da_auction.marketType = MarketTypes.auction
    prior_da_auction.name = 'Prior DA Market'
    prior_da_auction.marketSeriesName = 'Day-Ahead Auction'
    prior_da_auction.nextMarketClearingTime = time
    prior_da_auction.intervalsToClear = 24
    prior_da_auction.intervalDuration = timedelta(hours=1)
    test_node.markets = [prior_da_auction]

    try:
        prior_da_auction.spawn_markets(this_transactive_node=test_node,
                                       new_market_clearing_time=time
                                       )
        print('  - The method ran without errors.')
    except RuntimeError as message:
        print('  - ERRORS WERE ENCOUNTERED: ', message)

    assert len(test_node.markets) == 98, 'An unexpected market count happened: ' + str(len(test_node.markets))
    assert sum(x.marketSeriesName == 'Day-Ahead Auction' for x in test_node.markets) == 2, \
        'There were an unexpected number of Day-Ahead markets: ' \
        + str(sum(x.marketSeriesName == "Day-Ahead Auction" for x in test_node.markets))
    assert sum(x.marketSeriesName == 'Real-Time Auction' for x in test_node.markets) == 96, \
        'There were an unexpected number of Real-Time markets: ' \
        + str(sum(x.marketSeriesName == "Real-Time Auction" for x in test_node.markets))

    print('test_spawn_markets() ran to completion.\n')


if __name__ == '__main__':
    print('Running tests in test_day_ahead_auction.py\n')
    test_spawn_markets()
    print('Tests in test_day_ahead_auction.py ran to completion.\n')
