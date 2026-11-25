aa = [0.195	0.951	102.448	0.082
0.161	0.246	6.397	0.068
0.195	0.630	22.658	0.067
0.100	4.658	107.515	0.056
0.183	1.218	10.993	0.079
0.176	0.841	5.321	0.069
0.124	0.661	3.252	0.069
0.104	0.172	1.282	0.061
0.142	0.091	2.154	0.096
0.151	0.108	0.190	0.057
0.128	0.084	0.080	0.075
0.150	0.090	0.092	0.082
0.155	0.093	0.094	0.094
0.158	0.102	0.104	0.102
0.190	0.127	0.128	0.129
0.145	0.097	0.102	0.099
0.162	0.117	0.214	0.100
0.163	0.193	1.714	0.118
0.157	0.242	1.546	0.110
0.212	0.311	2.814	0.157
0.204	0.200	2.349	0.137
0.223	0.163	0.778	0.163
0.270	0.243	6.787	0.190
0.251	0.265	6.409	0.176];


gf = figure(253); hold off

l= [         0    0.4470    0.7410
    0.8500    0.3250    0.0980
    0.9290    0.6940    0.1250
    0.4940    0.1840    0.5560];

markert = {'-o';'-*';'-<';'--';'-';'--'};


for i = 1:4
    
    plot(aa(:,i),markert{i},'LineWidth',1.5,'Color',l(i,:))
    hold on
end


grid on
xlabel('Pose')
ylabel('RMS error [mm]')
title('RMS fitting error of a mirror ')
% 
% legend('mean RMSe \phi vs X', 'max RMSe \phi vs X', ...
%        'mean RMSe \phi vs Y', 'max RMSe \phi vs Y', ...
%        'mean RMSe \phi vs Z', 'max RMSe \phi vs Z')


% legend('mean RMSe \phi(u,v) vs X(u,v)', 'max RMSe \phi(u,v) vs X(u,v)', ...
%        'mean RMSe \phi(u,v) vs Y(u,v)', 'max RMSe \phi(u,v) vs Y(u,v)', ...
%        'mean RMSe \phi(u,v) vs Z(u,v)', 'max RMSe \phi(u,v) vs Z(u,v)')

legend('Stereo', ...
       'exp-POL3', ...
       'exp-POL6', ...
       'Proposed')



gf.Children(1).FontSize = 12;
gf.Children(2).FontSize = 14;