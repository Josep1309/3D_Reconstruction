



syms F1 F2 F3 F4 F5 F6 F7 F8 F9 F10  Z1 Z2 Z3 Z4   


M = [F1 F2 F3 F4;
       F2 F5 F6 F7;
       F3 F6 F8 F9;
       F4 F7 F9 F10];

b = [Z1; Z2; Z3;Z4];

dete = det(M);

sol = M\b*det(M);


sola = ['a =' char(sol(1)) ';'];
solb = ['b =' char(sol(2)) ';'];
solc = ['c =' char(sol(3)) ';'];
sold = ['d =' char(sol(4)) ';'];
detA =  ['dete =' char(dete) ';'];

text1 =[detA sola solb solc sold];
%%



text1 = strrep(text1,'*','.*');

for i=1:10
text1 = strrep(text1,['F',num2str(i),'^2'],['F',num2str(i),'.*F',num2str(i),]);
end

C = strsplit(text1,';');

%%



