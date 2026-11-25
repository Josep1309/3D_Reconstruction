%% Generamos las variables simbolicas
grado = 7;
Fs = sym(zeros([1,2*grado]));
for i = (1:(2*grado+1))-1

eval(['syms F',num2str(i)])
eval(['Fs(i+1) = F',num2str(i),';'])
end

for i = (1:(grado+1))-1

eval(['syms Z',num2str(i)])
end
%% Creamos la matriz y vector para la solucion por LMS

M = sym(zeros(grado+1,grado+1));
for i = 1:(grado+1)
    for j = 1:(grado+1)
        eval(['aux = F',num2str(grado+grado+2-i-j),';'])
        M(i,j) = aux;
    end
end

Z = sym(zeros(grado+1,1));
for i = 1:(grado+1)
        eval(['aux = Z',num2str(grado+1-i),';'])
        Z(i) = aux;
end
%% Calcular los determinantes
Detes = {};


sola = M ; sola(:,1) = Z; sola=det(sola);
detM = det(M);
for i = (1:(2*grado+1))
    sola = collect(sola,Fs(i));
    detM = collect(detM,Fs(i));
    disp(i)
end
% sola = collect(collect(collect(collect(collect(collect(collect(collect(collect(sola,F4),F5),F3),F2),F1),F9),F8),F7),F10);

detM = ['detM =' char(detM) ';']; sola = ['a =' char(sola) ';'];


text1 =[detM sola];
 %%

 
text1 = strrep(text1,'*','.*');

for i=1:16
    text1 = strrep(text1,['F',num2str(i),'^2'],['F',num2str(i),'_2']);
    text1 = strrep(text1,['F',num2str(i),'^3'],['F',num2str(i),'_3']);
    text1 = strrep(text1,['F',num2str(i),'^4'],['F',num2str(i),'_2','.*F',num2str(i),'_2']);
    text1 = strrep(text1,['F',num2str(i),'^5'],['F',num2str(i),'_3','.*F',num2str(i),'_2']);
    text1 = strrep(text1,['F',num2str(i),'^6'],['F',num2str(i),'_3','.*F',num2str(i),'_3']);
    text1 = strrep(text1,['F',num2str(i),'^7'],['F',num2str(i),'_3','.*F',num2str(i),'_3.*F',num2str(i),'']);
end


C = strsplit(text1,';');
 %%

arcID = fopen('a.txt','w');

fprintf(arcID,'%s \n %s \n', C{1}, C{2});
%%


syms c7 c6 c5 c4 c3 c2 c1 c0 mX sX X

z = c7*X^7+c6*X^6+c5*X^5+c4*X^4+c3*X^3+c2*X^2+c1*X+c0;

z2 = subs(z,'X',(X-mX)/sX);

z2 = collect(z2,'X');

coef = coeffs(z2,'X');
grado =7;
C2 = '';
for i =1:(grado+1)
    
    C2 = [C2,'c',num2str(i-1),'=',char(coef(i)),';'];
%     C2 = strrep(C2,['sX^',num2str(i)],['sX',num2str(i)]);
%     C2 = strrep(C2,['mX^',num2str(i)],['mX',num2str(i)]);

end

C2 = strrep(C2,'*','.*');
C2 = strrep(C2,'/','./');
C2 = strrep(C2,'^','');
C2 = strsplit(C2,';');

c0=c0 - (c1.*mX1)./sX1 + (c2.*mX2)./sX2 - (c3.*mX3)./sX3 + (c4.*mX4)./sX4 - (c5.*mX5)./sX5 + (c6.*mX6)./sX6 - (c7.*mX7)./sX7;
c1=c1./sX1 - (2.*c2.*mX1)./sX2 + (3.*c3.*mX2 )./sX3 - (4.*c4.*mX3 )./sX4 + (5.*c5.*mX4 )./sX5 - (6.*c6.*mX5 )./sX6 + (7.*c7.*mX6)./sX7;
c2=c2./sX2 - (3.*c3.*mX1)./sX3 + (6.*c4.*mX2 )./sX4 - (10.*c5.*mX3)./sX5 + (15.*c6.*mX4)./sX6 - (21.*c7.*mX5)./sX7;
c3=c3./sX3 - (4.*c4.*mX1)./sX4 + (10.*c5.*mX2)./sX5 - (20.*c6.*mX3)./sX6 + (35.*c7.*mX4)./sX7;
c4=c4./sX4 - (5.*c5.*mX1)./sX5 + (15.*c6.*mX2)./sX6 - (35.*c7.*mX3)./sX7;
c5=c5./sX5 - (6.*c6.*mX1)./sX6 + (21.*c7.*mX2)./sX7;
c6=c6./sX6 - (7.*c7.*mX1)./sX7;
c7=c7./sX7;

% g = g - (f*mX)/sX + (a*mX^6)/sX^6 - (b*mX^5)/sX^5 + (c*mX^4)/sX^4 - (d*mX^3)/sX^3 + (e*mX^2)/sX^2;
% f = f/sX - (2*e*mX)/sX^2 - (6*a*mX^5)/sX^6 + (5*b*mX^4)/sX^5 - (4*c*mX^3)/sX^4 + (3*d*mX^2)/sX^3;
% e = e/sX^2 - (3*d*mX)/sX^3 + (15*a*mX^4)/sX^6 - (10*b*mX^3)/sX^5 + (6*c*mX^2)/sX^4;
% d = d/sX^3 - (4*c*mX)/sX^4 - (20*a*mX^3)/sX^6 + (10*b*mX^2)/sX^5;
% c = c/sX^4 - (5*b*mX)/sX^5 + (15*a*mX^2)/sX^6;
% b = b/sX^5 - (6*a*mX)/sX^6;
% a = a/sX^6;






