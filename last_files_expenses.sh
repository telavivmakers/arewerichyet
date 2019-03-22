#!/bin/bash

function error() {
	echo $@
	exit -1
}

(which xsv 2> /dev/null > /dev/null) || error install rust and xsv

xsv cat rows $(find . -maxdepth 1 -ctime -14 -iname 'fibi_last_month*.csv') | xsv sort | uniq \
| xsv select expense,value_date $f | grep -v '^,' > last_expenses.csv
xsv join --left expense last_expenses.csv  cost recurring_by_cost.csv  | xsv select expense,value_date,recurring > last_expenses_with_recurring.csv
xsv join --left expense,value_date last_expenses_with_recurring.csv expense,value_date one_time.csv \
  |  xsv select expense,value_date,recurring,one_time

