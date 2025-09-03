#!/bin/bash
# Fix budget cost_filter syntax
sed -i '/cost_filter {/,/^  }/c\
  cost_filter {\
    name   = "Service"\
    values = ["AWS Lambda"]\
  }' modules/monitoring/budget.tf
