



syms F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 F13 F14 F15  Z1 Z2 Z3 Z4 Z5  


M = [  F1 F2 F3  F4  F5;
       F2 F6 F7  F8  F9;
       F3 F7 F10 F11 F12;
       F4 F8 F11 F13 F14;
       F5 F9 F12 F14 F15];

b = [Z1; Z2; Z3;Z4;Z5];

dete = det(M);

sol = M\b*det(M);


sola = ['a =' char(sol(1)) ';'];
solb = ['b =' char(sol(2)) ';'];
solc = ['c =' char(sol(3)) ';'];
sold = ['d =' char(sol(4)) ';'];
sole = ['e =' char(sol(5)) ';'];

detA =  ['dete =' char(dete) ';'];

text1 =[detA sola solb solc sold sole];
%%



text1 = strrep(text1,'*','.*');

for i=1:15
text1 = strrep(text1,['F',num2str(i),'^2'],['F',num2str(i),'.*F',num2str(i),]);
end

C = strsplit(text1,';');

%%

syms a b c d e mX sX X a2 b2 c2 d2 e2

z = (a+b*X+c*X*X)/(1+d*X+e*X*X);

z2 = subs(z,'X',(X-mX)/sX);


z3 = (a2+b2*X+c2*X*X)/(1+d2*X+e2*X*X);

% z4 = (c*X^2 + *X + )/(e*X^2 + *X + );


cons = e*mX.*mX - d*mX*sX + sX.*sX;
a2 = (c*mX.*mX - b*mX*sX + a*sX.*sX)./cons;
b2 = (b*sX - 2*c*mX)./cons;
c2 = c./cons;
d2 = (d*sX - 2*e*mX)./cons;
e2 = e./cons;





