set terminal png nocrop enhanced font arial 8 size 1280,1024
set output 'output/mc_quartiles.png'
set boxwidth 0.4 absolute
set xrange [ 0: ] noreverse nowriteback
set style fill empty
set offset 0,0.5,0,0
set title "LISA with Monte Carlo Simulation"
set ylabel "Calculation Time (in seconds)"
set xlabel "Number of Cluster Nodes"
set style line 2 lc rgb 'black' lt 1 lw 2 pt 7 pi -1 ps 1.5
plot 'data/mc_comb.dat' using 1:3:2:6:5:xticlabels(9) with candlesticks lt 3 lw 2 title 'Quartiles' whiskerbars, \
    '' u 1:4 with lp lw 2 title "Average Calculation Time"
    #'' using 1:4:4:4:4 with candlesticks lt -1 lw 2 notitle