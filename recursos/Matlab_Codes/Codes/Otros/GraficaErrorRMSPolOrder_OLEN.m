aa = [2	0.5281	1.0673	0.3961	0.8285	4.7352	4.7778;
3	0.0967	0.1954	0.0724	0.1515	0.8671	0.8781;
4	0.0175	0.0354	0.0131	0.0274	0.1573	0.1598;
5	0.0031	0.0064	0.0024	0.0049	0.0282	0.0288;
6	0.0006	0.0011	0.0004	0.0009	0.0050	0.0051];


gf = figure(252); hold off

l= [         0    0.4470    0.7410;
             0    0.4470    0.7410;
    0.8500    0.3250    0.0980;
    0.8500    0.3250    0.0980;
    0.9290    0.6940    0.1250;
    0.9290    0.6940    0.1250];

markert = {'-';'--';'-';'--';'-';'--'};


for i = [2:2:7]
    
    plot(aa(:,1),aa(:,i),'LineWidth',1.5,'Marker','o','Color',l(i-1,:),'LineStyle',markert{i-1})
    hold on
end


grid on
xlabel('Polynomial Order')
ylabel('RMS error [mm]')
title('Average of fitting RMSE ')
% 
% legend('mean RMSe \phi vs X', 'max RMSe \phi vs X', ...
%        'mean RMSe \phi vs Y', 'max RMSe \phi vs Y', ...
%        'mean RMSe \phi vs Z', 'max RMSe \phi vs Z')


% legend('mean RMSe \phi(u,v) vs X(u,v)', 'max RMSe \phi(u,v) vs X(u,v)', ...
%        'mean RMSe \phi(u,v) vs Y(u,v)', 'max RMSe \phi(u,v) vs Y(u,v)', ...
%        'mean RMSe \phi(u,v) vs Z(u,v)', 'max RMSe \phi(u,v) vs Z(u,v)')

legend('\phi(u,v) vs X(u,v)', ...
       '\phi(u,v) vs Y(u,v)', ...
       '\phi(u,v) vs Z(u,v)')



gf.Children(1).FontSize = 12;
gf.Children(2).FontSize = 14;