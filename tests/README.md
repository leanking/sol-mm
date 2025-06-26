# Market Maker Testing Guide

This directory contains comprehensive tests for the Hyperliquid Market Maker system. These tests are designed to validate the system before production deployment.

## Test Suite Overview

### 1. Unit Tests (`test_strategy.py`)
- **Purpose**: Test individual components in isolation
- **Scope**: Strategy calculations, risk management, volatility calculations
- **Risk Level**: None (uses mocked data)
- **Duration**: ~30 seconds

### 2. Integration Tests (`test_integration.py`)
- **Purpose**: Test system components working together with real API calls
- **Scope**: Exchange connectivity, market data retrieval, strategy execution
- **Risk Level**: Low (read-only operations)
- **Duration**: ~2-3 minutes

### 3. Stress Tests (`test_stress.py`)
- **Purpose**: Test system behavior under adverse conditions
- **Scope**: Rapid updates, concurrent operations, error handling
- **Risk Level**: Low (read-only operations)
- **Duration**: ~3-5 minutes

### 4. Paper Trading (`test_paper_trading.py`)
- **Purpose**: Simulate market making without real trades
- **Scope**: Complete market making cycle simulation
- **Risk Level**: None (simulation only)
- **Duration**: Configurable (default: 30 minutes)

### 5. Production Readiness (`test_production_readiness.py`)
- **Purpose**: Validate system readiness for production deployment
- **Scope**: Security, configuration, performance, monitoring
- **Risk Level**: Low (read-only operations)
- **Duration**: ~2-3 minutes

## Quick Start

### Run All Tests
```bash
cd tests
python run_all_tests.py
```

### Run Individual Test Suites
```bash
# Unit tests (fastest, safest)
python test_strategy.py

# Integration tests (real API calls)
python test_integration.py

# Stress tests (adverse conditions)
python test_stress.py

# Paper trading simulation
python test_paper_trading.py

# Production readiness checklist
python test_production_readiness.py
```

## Test Execution Order

For best results, run tests in this order:

1. **Unit Tests** - Verify basic functionality
2. **Integration Tests** - Verify real API integration
3. **Stress Tests** - Verify system stability
4. **Paper Trading** - Simulate actual trading (optional)
5. **Production Readiness** - Final validation

## Prerequisites

### Environment Setup
1. Ensure your `.env` file is properly configured
2. Verify API keys are set and valid
3. Check that all dependencies are installed

### Required Dependencies
```bash
pip install psutil  # For memory monitoring in stress tests
```

## Test Results Interpretation

### Success Criteria
- **Unit Tests**: All tests should pass
- **Integration Tests**: >90% success rate
- **Stress Tests**: <5% error rate
- **Production Readiness**: >85% readiness score

### Common Issues

#### API Rate Limits
- **Symptom**: Tests fail with timeout or rate limit errors
- **Solution**: Add delays between API calls or reduce test frequency

#### Network Connectivity
- **Symptom**: Connection errors or timeouts
- **Solution**: Check internet connection and firewall settings

#### Configuration Issues
- **Symptom**: Missing environment variables or invalid config
- **Solution**: Verify `.env` file and `config.json` are properly set

## Paper Trading Simulation

The paper trading test simulates market making without placing real orders:

```bash
python test_paper_trading.py
```

### Configuration Options
- **Duration**: Default 30 minutes (configurable)
- **Update Interval**: Default 30 seconds (configurable)
- **Starting Balance**: $10,000 USDC (configurable)

### Output
- Real-time status updates
- Trade simulation results
- PnL tracking
- JSON report file

## Production Readiness Checklist

The production readiness test validates:

### Security
- API key configuration
- Environment variable usage
- Access control

### Risk Management
- Position size limits
- Drawdown limits
- Leverage controls

### Configuration
- All required settings
- Valid parameter ranges
- Consistency checks

### Performance
- Response time benchmarks
- Memory usage
- API success rates

### Reliability
- Error handling
- Recovery mechanisms
- System stability

### Monitoring
- Logging configuration
- Log file creation
- Error tracking

## Continuous Testing

### Automated Testing
For continuous integration, you can run:

```bash
# Run all tests and generate report
python run_all_tests.py

# Run specific test with output
python -m unittest tests.test_integration -v

# Run with coverage (if coverage.py is installed)
coverage run -m unittest discover tests
coverage report
```

### Monitoring
- Check test results regularly
- Monitor for new failures
- Track performance metrics
- Review error logs

## Troubleshooting

### Test Failures

#### Integration Test Failures
1. Check API connectivity
2. Verify API keys are valid
3. Check rate limits
4. Review error messages

#### Stress Test Failures
1. Check system resources
2. Verify network stability
3. Review memory usage
4. Check for resource leaks

#### Production Readiness Failures
1. Review failed checklist items
2. Fix configuration issues
3. Address security concerns
4. Improve error handling

### Performance Issues
1. Monitor system resources
2. Check API response times
3. Review memory usage
4. Optimize code if needed

## Best Practices

### Before Running Tests
1. Ensure clean environment
2. Check all dependencies
3. Verify configuration
4. Test with small datasets first

### During Testing
1. Monitor system resources
2. Watch for error patterns
3. Document any issues
4. Save test results

### After Testing
1. Review all results
2. Address any failures
3. Update documentation
4. Plan next steps

## Deployment Checklist

Before deploying to production:

- [ ] All unit tests pass
- [ ] Integration tests >90% success rate
- [ ] Stress tests <5% error rate
- [ ] Production readiness >85% score
- [ ] Paper trading simulation completed
- [ ] All configuration validated
- [ ] Security review completed
- [ ] Monitoring setup verified
- [ ] Backup procedures tested
- [ ] Rollback plan prepared

## Support

If you encounter issues:

1. Check the logs in the `logs/` directory
2. Review test output for error messages
3. Verify configuration and environment
4. Check API documentation for changes
5. Review system requirements

## Test Reports

All tests generate detailed reports:

- **JSON Reports**: Detailed test results and metrics
- **Log Files**: Comprehensive logging of all operations
- **Console Output**: Real-time status and progress
- **Summary Reports**: High-level pass/fail status

Reports are saved with timestamps for historical tracking and analysis. 