%%
% En este script se realiza la solucion de ajuste fraccionado de las fase
% vs coordenadas de la camara, segun la funcion:
%   
%                  a + b*u + c*v + d*u^2 + e*u*v + f*v^2 
%  phi(u,v) =  --------------------------------------------
%                  1 + g*u + h*v + i*u^2 + j*u*v + k*v^2 
%
% La solucion se realiza por minimos cuadrados


string = '';
for i = 1:55
    string = [string,' F',num2str(i)];
end
eval(['syms' string])

syms Z1 Z2 Z3 Z4 Z5 Z6 Z7 Z8 Z9 Z10

syms u v phi

vect = [1 u v u^2 u*v v^2 -u*phi -v*phi -u^2*phi -u*v*phi -v^2*phi];

mat = vect'*vect;


M = [F1  F2  F3  F4  F5  F6  F7  F8  F9  F10;
     F2  F11 F12 F13 F14 F15 F16 F17 F18 F19;
     F3  F12 F20 F21 F22 F23 F24 F25 F26 F27;
     F4  F13 F21 F28 F29 F30 F31 F32 F33 F34;
     F5  F14 F22 F29 F35 F36 F37 F38 F39 F40; 
     F6  F15 F23 F30 F36 F41 F42 F43 F44 F45;
     F7  F16 F24 F31 F37 F42 F46 F47 F48 F49;
     F8  F17 F25 F32 F38 F43 F47 F50 F51 F52;
     F9  F18 F26 F33 F39 F44 F48 F51 F53 F54;
     F10 F19 F27 F34 F40 F45 F49 F52 F54 F55;]; 

b = [Z1;Z2;Z3;Z4;Z5;Z6;Z7;Z8;Z9;Z10];


sol = M\b;
dete = det(M);


sola = ['a =' char(sol(1)) ';'];
solb = ['b =' char(sol(2)) ';'];
solc = ['c =' char(sol(3)) ';'];
sold = ['d =' char(sol(4)) ';'];
sole = ['e =' char(sol(5)) ';'];
solf = ['f =' char(sol(6)) ';'];
solg = ['g =' char(sol(7)) ';'];
solh = ['h =' char(sol(8)) ';'];
soli = ['i =' char(sol(9)) ';'];
solj = ['j =' char(sol(10)) ';'];

text1 =[detA sola solb solc sold sole solf solg solh soli solj];




text1 = strrep(text1,'*','.*');

for i=1:55
text1 = strrep(text1,['F',num2str(i),'^2'],['F',num2str(i),'.*F',num2str(i),]);
end

C = strsplit(text1,';');














